# WebSocket protocol

Endpoint: `GET /ws/chat?ticket=<ticket>` (upgrade)

## Authentication

Browsers cannot set an `Authorization` header on a WebSocket, and long-lived JWTs must not appear in
URLs (they end up in proxy/access logs). So:

1. Client calls `POST /api/v1/auth/ws-ticket` with `Authorization: Bearer <access token>`.
   Response: `{"ticket": "...", "expires_in": 30}`.
2. Client connects to `/ws/chat?ticket=<ticket>` within 30 s. A ticket is **single-use**.
3. The server also checks the `Origin` header against `FRONTEND_ORIGIN` (protection against
   cross-site WebSocket hijacking — CORS does not apply to WebSockets).

The sender of every event is the authenticated user. Client payloads are validated with
`extra="forbid"`, so a client-supplied `sender_id`/`user_id` is rejected.

| Close code | Meaning |
|---|---|
| 4401 | Ticket missing, invalid, expired or already used (an `error` event with `code: "unauthorized"` is sent first) |
| 4403 | Origin not allowed |
| 4408 | Idle timeout: nothing received for `WS_IDLE_TIMEOUT_SECONDS` (default 60) — send `ping` every ~25 s |
| 1013 | Server closed a slow client whose outbound queue overflowed |
| 4410 | The account was deleted (`DELETE /api/v1/users/me`) |

## Envelopes

Client → server:

```json
{"type": "message.send", "id": "client-correlation-id", "payload": { ... }}
```

| Field | Rules |
|---|---|
| `type` | required, one of the client event types below |
| `id` | optional string ≤ 64 chars; echoed back as `correlation_id` |
| `payload` | object; validated per type; unknown fields rejected |

Frames larger than `WS_MAX_MESSAGE_BYTES` (16 KiB) are rejected with `payload_too_large`.

Server → client:

```json
{"type": "message.created", "id": "server-event-id", "correlation_id": "client-correlation-id-or-null",
 "payload": { ... }, "ts": "2026-10-10T07:30:00.123456+00:00"}
```

## Client events

| Type | Payload | Notes |
|---|---|---|
| `message.send` | `conversation_id: uuid`, `text: string (1..MAX_MESSAGE_LENGTH after trim)`, `client_message_id: string (1..64)`, `source_language?: code` | If `source_language` is omitted it is detected from the text's script (Latin → English, Gujarati → Gujarati, Devanagari → sender's Devanagari language or Hindi, …); romanized Indic text is detected as English. Idempotent on `(sender, client_message_id)`; retries return the original message with `duplicate: true`. Rate limit: `WS_MESSAGES_PER_10S`. |
| `message.read` | `conversation_id: uuid`, `message_id: uuid` | Marks that message and every earlier one in the conversation as read for the caller. |
| `typing.start` / `typing.stop` | `conversation_id: uuid` | Clients should throttle (the web client sends at most every 3 s). Receivers expire indicators after ~6 s. |
| `ping` | `{}` | Answered with `pong`. Keeps the idle timer alive. |

## Server events

| Type | Payload | Sent to |
|---|---|---|
| `session.ready` | `user_id`, `online_user_ids` (contacts only), `heartbeat_seconds` | the new connection |
| `message.created` | `message: Message`, `duplicate: bool` | sender (with `correlation_id` = ack) and all other members |
| `message.translated` | `Translation` + `conversation_id` | all conversation members, each time a translation changes state (`pending` on retry, then `completed`/`failed`) |
| `message.delivered` | `conversation_id`, `message_ids[]`, `user_id` (recipient), `delivered_at` | the sender(s) |
| `message.read` | `conversation_id`, `user_id` (reader), `message_ids[]`, `up_to_message_id`, `read_at` | all members |
| `typing.started` / `typing.stopped` | `conversation_id`, `user_id` | other members |
| `presence.updated` | `user_id`, `online`, `last_seen_at` | users who share a conversation |
| `conversation.removed` | `conversation_id`, `reason: "account_deleted"` | the other members — the conversation and all its messages were erased |
| `user.updated` | `user: User` | users who share a conversation |
| `pong` | `{}` | the pinging connection |
| `error` | `code`, `message`, `details?` | the connection whose event failed (with `correlation_id`) |

### Message

```json
{
  "id": "uuid", "conversation_id": "uuid", "sender_id": "uuid", "client_message_id": "string|null",
  "original_text": "તમે કેમ છો?", "source_language": "guj_Gujr", "created_at": "ISO-8601 UTC",
  "status": "sent|delivered|read",
  "translations": [Translation]
}
```

`status` aggregates all recipients' receipts (meaningful for the sender's own messages).

### Translation

```json
{
  "id": "uuid", "message_id": "uuid", "target_language": "hin_Deva",
  "translated_text": "आप कैसे हैं?",      // null unless status == "completed"; never empty when completed
  "model_name": "ai4bharat/indictrans2-indic-indic-dist-320M",
  "status": "pending|completed|failed", "error_message": "string|null", "translated_at": "ISO|null"
}
```

## Delivery flow

```
client A                      server                                   client B
   | message.send ------------> | validate membership, persist message,
   |                            | receipts + pending translation rows (1 tx)
   | <---- message.created (ack)| ----- message.created (original, pending) ----> |
   |                            | translate in worker thread (bounded queue)
   | <---- message.translated --| ----- message.translated (completed|failed) --> |
```

The original message is delivered immediately; translation never delays or blocks delivery. If B is
offline, everything is in PostgreSQL and is returned by `GET /api/v1/conversations/{id}/messages`
(which also marks the messages delivered and notifies A with `message.delivered`).

Failed translations are retried with `POST /api/v1/messages/{id}/translations/retry`
(optionally `{"target_language": "..."}` to translate into a language that has no translation yet,
e.g. after the reader changed their preferred language).

## Error codes

`invalid_event`, `unknown_event`, `validation_error`, `payload_too_large`, `rate_limited`,
`conversation_not_found` (also used for "not a member" so IDs can't be probed), `message_not_found`,
`empty_message`, `message_too_long`, `recipient_deleted`, `duplicate_client_message_id`, `internal_error`, `unauthorized`.

## Reconnection (web client behaviour)

- Exponential backoff with jitter (1 s → 30 s), immediate retry on the browser `online` event.
- A fresh ticket for every attempt (refreshing the access token via the refresh cookie if needed).
- If no frame arrives for 2 heartbeat intervals the socket is considered half-open and recycled.
- After `session.ready` the client re-fetches conversations and the open conversation's latest page
  and re-sends unacknowledged messages with the **same** `client_message_id` (no duplicates).

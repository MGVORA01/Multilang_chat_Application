# Architecture

```
 Browser (React + TS)                       FastAPI process (uvicorn, 1 worker)                PostgreSQL
 ┌───────────────────┐  REST /api/v1  ┌─────────────────────────────────────────────┐  asyncpg  ┌──────────┐
 │ zustand stores    │ ─────────────► │ routers → services → repositories (SQLA 2)  │ ────────► │ users     │
 │ axios (+refresh)  │                │                                             │           │ convs     │
 │ ChatSocket        │ ◄────WS──────► │ /ws/chat → ConnectionManager (in-memory)    │           │ messages  │
 └───────────────────┘                │        ↘ MessagingService                   │           │ transl.   │
                                      │            ↘ TranslationService             │           │ receipts  │
                                      │               bounded queue + semaphore     │           └──────────┘
                                      │               ThreadPoolExecutor (N=1)       │
                                      │                 ↘ IndicTrans2Engine          │
                                      │                    3 checkpoints, 1 lock each│
                                      └─────────────────────────────────────────────┘
```

## Backend layout (`backend/app`) — feature modules, Router → Service → Repository

```
app/
├── main.py                 app factory + lifespan: builds singletons on app.state
├── api/                    router.py (mounts every feature under /api/v1), dependencies.py (session, singletons, rate limits)
├── core/                   config, security (Argon2id/JWT), exceptions (+ error envelope), logging, metrics,
│                           rate_limit, languages (catalog + validator)
├── db/                     declarative base, async engine/session factory
├── models/                 registry that imports every feature's models (Alembic metadata)
├── shared/                 schemas.py (ApiModel, Page, CursorPage, payload helpers), tasks.py (BackgroundTasks)
├── integrations/translation/   base.py (engine contract, ModelRegistry routing, errors), indictrans2.py, mock.py,
│                               disabled.py, factory.py (picks the engine from TRANSLATION_BACKEND)
├── features/
│   ├── auth/           router · service (register/login/refresh rotation/logout) · repository (refresh tokens)
│   │                   · models (RefreshToken) · schemas · dependencies (CurrentUser)
│   ├── users/          router · service (search, profile, language, hard delete) · repository · models (User)
│   │                   · schemas · serializers
│   ├── conversations/  router · service (list, get-or-create direct, require_membership) · repository
│   │                   · models (Conversation, ConversationMember) · schemas · serializers
│   ├── messages/       router (history, retry) · service (send, history, receipts, typing)
│   │                   · translation_jobs (pending rows, background runs, retry) · repository
│   │                   · models (Message, MessageTranslation, MessageReceipt, TranslationStatus) · schemas · serializers
│   ├── translation/    router (POST /translations, GET /translations/{id}) · service (bounded async TranslationService)
│   │                   · language_detection (script-based source language) · schemas
│   ├── presence/       service (online/offline + last seen, contacts only)
│   └── system/         router (languages, health, metrics) · schemas
└── websocket/          router.py (connection lifecycle) · handlers.py (frame validation + dispatch)
                        · manager.py (connections, per-socket send queues) · protocol.py (envelopes, payloads,
                        ClientEvent / ServerEvent / CloseCode enums) · tickets.py
```

Rules: routers only parse/validate and call one service method; services own business rules and
transaction boundaries (`commit`); repositories only build queries (`add`/`flush`, never `commit`).
Feature modules depend "downwards" (messages → conversations → users), never in a cycle.

### Request flows

```
REST:  React feature hook/store → feature api.ts → services/api/client (axios, auto-refresh)
       → features/<x>/router → <x>Service → repository → PostgreSQL → serializers → response

WS:    Composer → chatStore.sendMessage → Outbox.transmit → ChatSocket
       → websocket/router (ticket + Origin) → handlers.FrameHandler (validate, rate-limit)
       → MessageService.send ─ persist message + receipts + pending translations (1 transaction)
                              ├─ ConnectionManager → message.created (sender ack + recipients)
                              └─ MessageTranslationService.schedule → TranslationService (thread pool)
                                   → persist result → message.translated → chatStore.serverEvents → UI
```

## Frontend layout (`frontend/src`)

```
app/            App.tsx (session bootstrap), router.tsx (routes + auth guards)
config/         environment-driven config (VITE_API_BASE_URL, VITE_WS_PATH)
constants/      MAX_MESSAGE_LENGTH, TIMING (typing, heartbeat, ack, preview debounce), WS_CLOSE codes, routes
components/ui/  Avatar, Button, EmptyState, ErrorBanner, Icon, LanguageSelect, Logo, Spinner, TextField
services/       api/client.ts (axios + single-flight token refresh), websocket/ChatSocket.ts (reconnect, heartbeat)
types/          domain.ts, api.ts, websocket.ts (typed event maps)
lib/            format.ts (dates/names), storage.ts (safe localStorage)
features/
  auth/           api, store (session), validation, components (AuthLayout, LoginPage, RegisterPage)
  conversations/  api (conversations, people search), preview, components (ConversationList, ConversationListItem,
                  UserSearchResults)
  chat/           api (history, retry), store (chatStore, serverEvents, outbox, messageMerge, types),
                  hooks (useChatConnection, useScrollAnchoring, useTypingNotifier, useNow),
                  components (ChatView, ChatHeader, MessageBubble, MessageMenu, DeliveryTicks, TypingIndicator,
                  Composer, TranslationPreviewBar, EmojiButton, EmojiPanel [lazy], ConnectionBadge)
  translation/    api (preview, languages), languages (catalog, detection, names), hooks (useTranslationPreview)
  profile/        api, components (SettingsPage, DeleteAccountSection)
pages/          MessengerPage (responsive two-panel shell)
```

Each feature exposes its public surface through `index.ts`; presentation components get data via
props/stores and call feature `api.ts` modules — never axios directly.

## Translation routing

| Source | Target | Checkpoint |
|---|---|---|
| `eng_Latn` | Indic | `ai4bharat/indictrans2-en-indic-dist-200M` |
| Indic | `eng_Latn` | `ai4bharat/indictrans2-indic-en-dist-200M` |
| Indic | Indic | `ai4bharat/indictrans2-indic-indic-dist-320M` |
| same language / disabled language | — | `unsupported_language_pair` |

Inference: `IndicProcessor.preprocess_batch` → tokenizer → `model.generate(num_beams=TRANSLATION_NUM_BEAMS)`
→ `batch_decode` → `IndicProcessor.postprocess_batch`. Float32 on CPU; no CUDA / flash-attention.

## Concurrency model

- Models load **once** at startup (sequentially, to avoid a memory spike), in a worker thread.
- `TranslationService.translate()` is async. Inference runs in a dedicated `ThreadPoolExecutor`
  (`TRANSLATION_MAX_CONCURRENT_JOBS`, default 1) so the event loop — and every other WebSocket —
  keeps running (covered by `test_event_loop_not_blocked_during_inference`).
- Each checkpoint has its own `threading.Lock`: `generate()` on a shared instance is not documented as
  thread-safe, so access per model is serialized even if concurrency is raised.
- At most `TRANSLATION_MAX_QUEUE_SIZE` jobs may be waiting or running; beyond that callers get
  `translation_queue_full` immediately (stored as a failed, retryable translation).
- `TRANSLATION_TIMEOUT_SECONDS` bounds how long a caller waits. Python cannot kill a running thread,
  so the concurrency slot is only released when the inference actually finishes.
- An LRU cache (`TRANSLATION_CACHE_SIZE`) avoids re-translating identical `(src, tgt, text)`.
- Pending jobs live in memory: on restart, `pending` rows are marked `failed` with a retry hint.

## Reliability guarantees

- The original message is committed (with receipts and `pending` translation rows) **before**
  anything is sent, and is never modified by translation.
- A failed/timed-out/empty translation becomes `status=failed` (DB check constraint forbids a
  `completed` row with empty text). The message is still delivered and shown in its original form.
- `client_message_id` + unique `(sender_id, client_message_id)` makes sends idempotent.
- `direct_key` (sorted user-id pair, unique) prevents duplicate direct conversations, even under races.
- Non-members get `404 conversation_not_found` (no existence oracle).

## Single-process limitations and how to scale out

The following are in-memory and therefore require **exactly one uvicorn worker**:

| Component | Multi-worker replacement |
|---|---|
| `ConnectionManager` (who is connected where) | Redis Pub/Sub: publish each event to `user:<id>`; every worker subscribes for its local users and forwards |
| Presence | Redis sets with TTL refreshed by heartbeats |
| WS tickets | Redis `SET ticket user_id EX 30` + `GETDEL` |
| Rate limiters | Redis sliding window / token bucket |
| Translation queue | dedicated translation worker process(es) consuming a Redis/Postgres-backed job queue, so API workers don't each load ~3 GB of models |

Since the delivery code only ever calls `manager.send_to_user(s)` with explicit user IDs, swapping in
a Redis-backed manager does not change the messaging services.

## Group conversations (future)

The schema already supports it: `conversation_type='group'`, `title`, N members, per-recipient
receipts, and one translation row per distinct target language (not per recipient). Remaining work:
group creation/membership endpoints and UI.

## Observability

- JSON logs to stdout. Message text, passwords and tokens are never logged.
- `GET /api/v1/metrics` (authenticated): counters (`messages_sent`, `translation_successes/failures/
  timeouts`, `ws_connects/disconnects`, `db_errors`, …), gauges (`ws_connections`,
  `translation_queue_length`), timings (`translation_seconds.<direction>`,
  `model_init_seconds.<direction>`, `message_processing_seconds`).
- `GET /api/v1/health`: database + per-model load state/errors.

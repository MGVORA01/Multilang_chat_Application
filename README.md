# Bhasha Chat — real-time multilingual messaging

Write in your language; the other person reads it in theirs. Messages are translated with
[AI4Bharat IndicTrans2](https://github.com/AI4Bharat/IndicTrans2) on CPU and delivered over WebSockets.

- **Frontend**: React 19 + TypeScript (strict) + Vite + Tailwind CSS + React Router + Axios + Zustand
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2 (async, asyncpg), Alembic, JWT + Argon2id
- **Database**: PostgreSQL
- **Translation**: IndicTrans2 distilled checkpoints via Transformers + IndicTransToolkit, CPU-only PyTorch

```
backend/   FastAPI, feature modules (Router → Service → Repository), Alembic, pytest (unit + integration), scripts
frontend/  React + TS, feature folders (api / store / hooks / components), shared ui kit, Vitest
docs/      setup.md · architecture.md (structure + data flows) · websocket-protocol.md
```

Quick start: see **[docs/setup.md](docs/setup.md)**.

## Features

- Registration / login / logout, rotating httpOnly refresh cookie, in-memory access token
- Account deletion (password-confirmed hard delete: the user, their sessions and all their direct conversations/messages are erased; the other person's chat disappears live)
- Preferred language at sign-up and in Settings (applies to future messages; per-message "Translate to …" for history)
- User search, direct conversations (deduplicated at the DB level)
- Real-time messaging over an authenticated WebSocket (single-use tickets, Origin check)
- Original text always stored and shown on demand; translations stored separately per target language
- Pending / failed translation states, retry without creating a new message
- Sent / delivered / read receipts, typing indicators, presence + last seen, unread counts
- Idempotent sends (`client_message_id`), offline outbox, automatic reconnect with backoff + heartbeat
- Cursor-paginated history, responsive desktop/mobile layout, keyboard-accessible UI
- Bounded, non-blocking translation queue; models loaded once; JSON logs, metrics and health endpoints

## Status

| Area | State |
|---|---|
| Backend (feature modules, API, WebSocket, schema) | ✅ 48 pytest tests pass (13 unit without DB + 35 integration on PostgreSQL); ruff clean; `alembic check` clean |
| Frontend (feature folders, ui kit) | ✅ 59 Vitest tests, strict TypeScript, oxlint 0 warnings, production build |
| Real IndicTrans2 inference | ✅ all 6 Gujarati/Hindi/English directions on CPU (~0.2–0.6 s per short message) |
| Two-user acceptance test (spec §14) | ✅ 14/14 on the live stack with the real model + 11/11 browser checks |
| CPU benchmark report (`scripts/benchmark_translation.py`) | ⏳ not yet run — latencies above come from the integration test |
| Docker Compose | ⚠️ provided but not verified (Docker is not installed on the dev machine) |

## Known limitations

- Single backend process: connection manager, presence, WS tickets, rate limits and translation queue are in memory (Redis design in `docs/architecture.md`).
- Translation jobs that are pending during a restart are marked failed (retryable), not resumed.
- `TRANSLATION_TIMEOUT_SECONDS` stops waiting but cannot abort a running CPU inference.
- One-to-one conversations only in the API/UI (schema is group-ready).
- No message editing/deletion, attachments or push notifications.
- Language changes do not retranslate history automatically (by design; per-message action available).

## Future improvements

Redis Pub/Sub + separate translation worker for horizontal scaling; INT8 dynamic quantization or
CTranslate2 export to cut CPU latency/RAM (would need quality re-validation); batching concurrent
requests per direction; group chats; Playwright browser E2E tests; Prometheus metrics.

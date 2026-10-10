# Local setup (Ubuntu, CPU only)

Tested with: Ubuntu 26.04, Python 3.11 (venv), Node 22 / npm 10, PostgreSQL 18.

## 1. Backend dependencies

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
# CPU-only PyTorch + IndicTrans2 stack (~1 GB download, no CUDA):
.venv/bin/pip install -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

`transformers` is pinned `<5`: version 5.x removed `transformers.tokenization_utils.PreTrainedTokenizerBase`,
which IndicTransToolkit 1.1.x imports. Python 3.11 is used because PyTorch / IndicTransToolkit wheels
are reliable there (the system Python 3.14 is newer than some of these packages).

## 2. Environment

```bash
cp backend/.env.example backend/.env   # skip if backend/.env already exists
```

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:password@host:port/db` | — |
| `JWT_SECRET_KEY` | ≥ 32 random chars: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` | — (required) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | token lifetimes | 30 / 14 |
| `COOKIE_SECURE` | `true` behind HTTPS | false |
| `FRONTEND_ORIGIN` | comma-separated allowed origins (CORS + WS Origin check) | `http://localhost:5173` |
| `SUPPORTED_LANGUAGES` | enabled IndicTrans2 codes (any of the 26 in `app/core/languages.py`) | 12 languages |
| `TRANSLATION_BACKEND` | `indictrans2` \| `mock` \| `disabled` | indictrans2 |
| `TRANSLATION_MAX_CONCURRENT_JOBS` | parallel inferences | 1 |
| `TRANSLATION_MAX_QUEUE_SIZE` | max waiting+running jobs | 50 |
| `TRANSLATION_TIMEOUT_SECONDS` | per-job wait limit | 120 |
| `TRANSLATION_PRELOAD` | load all 3 checkpoints at startup | true |
| `TRANSLATION_TORCH_THREADS` | `torch.set_num_threads` | 4 |
| `TRANSLATION_NUM_BEAMS` | beam search width (quality vs. speed) | 3 |
| `INDIC_INDIC_MODEL` / `EN_INDIC_MODEL` / `INDIC_EN_MODEL` | checkpoint IDs | AI4Bharat distilled models |
| `WS_IDLE_TIMEOUT_SECONDS`, `WS_TICKET_EXPIRE_SECONDS`, `MAX_MESSAGE_LENGTH`, `AUTH_RATE_LIMIT_PER_MINUTE` | limits | 60, 30, 2000, 10 |

Frontend: `frontend/.env` is optional (`VITE_BACKEND_URL`, default `http://localhost:8000`).

## 3. PostgreSQL

```bash
bash backend/scripts/create_database.sh     # uses sudo -u postgres; reads user/password/db from backend/.env
cd backend && .venv/bin/alembic upgrade head
```

The script creates the role, the app database and `<db>_test` (used by pytest — it is wiped on each run).

## 4. Hugging Face access (IndicTrans2 checkpoints are gated)

1. Log in at https://huggingface.co and open each model page, then accept the terms
   ("Agree and access repository"):
   - https://huggingface.co/ai4bharat/indictrans2-indic-indic-dist-320M
   - https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M
   - https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M
2. Create a **Read** token at https://huggingface.co/settings/tokens.
3. `backend/.venv/bin/hf auth login` and paste the token (stored in `~/.cache/huggingface/token`,
   outside the repo). Never put it in `.env` or Git.
4. Check: `backend/.venv/bin/hf auth whoami`.

The first backend start downloads ~2.5 GB into `~/.cache/huggingface/hub`. If access is denied,
the server still starts; `/api/v1/health` shows the model `error`, and messages are delivered in
their original language with a "Translation unavailable" notice.

## 5. Run

```bash
# terminal 1 (--reload restarts automatically when backend code changes; omit in production)
cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload
# terminal 2
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. API docs: http://localhost:8000/api/docs.
Keep **one** uvicorn worker (see `docs/architecture.md`).

No model yet? Start with `TRANSLATION_BACKEND=mock .venv/bin/uvicorn app.main:app` — the UI then
shows `[hin_Deva] original text` as the "translation".

## 6. Tests and checks

```bash
cd backend
.venv/bin/pytest tests/unit                       # fast, no database needed
TEST_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/multilingual_chat_test .venv/bin/pytest   # unit + integration
.venv/bin/ruff check app tests scripts            # lint (config in ruff.toml)
DATABASE_URL=...multilingual_chat_test .venv/bin/alembic check   # models == migrations
# real model (slow, needs HF access):
RUN_MODEL_TESTS=1 TEST_DATABASE_URL=... .venv/bin/pytest tests/test_model_integration.py -s
# CPU benchmark -> docs/benchmark-results.md
.venv/bin/python -m scripts.benchmark_translation --runs 3
# two-user acceptance test against the running stack
.venv/bin/python -m scripts.e2e_acceptance --base http://localhost:5173 --db postgresql://USER:PASSWORD@localhost:5432/multilingual_chat

cd ../frontend
npm test            # vitest
npm run typecheck && npm run lint && npm run build
```

## 7. Docker (optional)

```bash
export POSTGRES_PASSWORD=$(python3 -c "import secrets;print(secrets.token_urlsafe(18))")
export HF_TOKEN=...          # from your credential store, not a file in the repo
docker compose up --build    # http://localhost:8080
```

## Production checklist

- HTTPS (terminate at nginx/Caddy), `COOKIE_SECURE=true`, `APP_ENV=production` (hides API docs).
- `FRONTEND_ORIGIN` set to the real origin only.
- Fresh `JWT_SECRET_KEY`; DB user with least privilege; backups.
- One uvicorn worker per the in-memory design, or implement the Redis layer first.
- Proxy must forward `Upgrade`/`Connection` headers for `/ws/` and keep read timeouts > 60 s.
- Size RAM from `docs/benchmark-results.md` (created by `scripts/benchmark_translation.py`; all three checkpoints stay loaded); the compose file caps the backend at 8 GB as a starting point.

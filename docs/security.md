# Security report

Audit date: 2026-10-10. Scope: `backend/` (FastAPI, SQLAlchemy, WebSocket, translation pipeline),
`frontend/` (React/TS), `docker-compose.yml`, Dockerfiles, `nginx.conf`, `.env*`, dependency manifests.
Method: manual review of every endpoint, WebSocket handler, repository query and config file, plus the
tools listed below. This is not a guarantee that no vulnerabilities remain.

## Threat model (summary)

- **Assets:** private messages and translations, account credentials/sessions, presence data, server CPU
  (translation model), the host (model code runs in-process).
- **Attackers:** any registered user (the main one: they hold a valid session), unauthenticated internet
  clients, a malicious website the victim visits (CSRF / cross-site WebSocket), a compromised upstream
  model repository (supply chain).
- **Trust boundaries:** browser ↔ API/WS; API ↔ PostgreSQL; app ↔ Hugging Face Hub / model code.

## Findings

| ID | Severity | Finding | Affected | Status |
|---|---|---|---|---|
| H1 | High | The `.env.example` placeholder JWT key (53 chars) passed validation; a deployment that copied it would let anyone forge tokens for any user. | `core/config.py` | **Fixed**: placeholder and low-entropy keys refused at startup. |
| H2 | High | Model checkpoints use `trust_remote_code=True` (repo Python runs in-process) **without revision pinning**: a compromised upstream repo would mean code execution on the next download. Bandit B615. | `integrations/translation/indictrans2.py` | **Fixed**: exact commits pinned (`*_MODEL_REVISION`); warning if unpinned. |
| M1 | Medium | No refresh-token reuse detection: a stolen refresh token stayed usable alongside the owner's. | `features/auth/service.py` | **Fixed**: reuse of a rotated token revokes every session of that user (`refresh_reused`). |
| M2 | Medium | Login limited per IP only, so distributed guessing against one account was unlimited. | `features/auth/service.py` | **Fixed**: per-account budget (`LOGIN_ATTEMPTS_PER_ACCOUNT_15MIN`). |
| M3 | Medium | Any user could see any other user's online status and last-seen via search/profile. | `features/users/*` | **Fixed**: presence only revealed to users sharing a conversation. |
| M4 | Medium | WebSocket abuse: send limit per *connection* (bypass with more sockets), unlimited sockets per user, unlimited ticket minting, unlimited typing/read events (each a DB query). | `websocket/*`, `features/auth/router.py` | **Fixed**: per-user send limit, per-connection event limit, max sockets per user (close 4429), ticket rate limit. |
| M5 | Medium | Translation abuse: retries unlimited (any of 11 target languages); preview/ad-hoc requests could fill the shared queue and starve real message translations. | `features/translation/*`, `features/messages/router.py` | **Fixed**: retries share the per-user inference budget; ad-hoc requests capped at `TRANSLATION_ADHOC_QUEUE_SHARE` of the queue. |
| M6 | Medium | No security headers; no request-body cap (whole body read into memory); uvicorn default 16 MB WS frames. | `main.py`, `nginx.conf`, Dockerfile | **Fixed**: headers middleware (nosniff, DENY, no-referrer, CSP, no-store on auth, HSTS in prod), 64 KB body cap enforced before parsing, `--ws-max-size 65536`, nginx headers + CSP (verified with the production build: 0 violations). |
| M7 | Medium | Unsafe production defaults could be deployed silently (`COOKIE_SECURE=false`, http origins, any Host). | `core/config.py` | **Fixed**: `APP_ENV=production` refuses to start unless HTTPS origins, secure cookies, explicit `ALLOWED_HOSTS` (TrustedHostMiddleware) and a non-placeholder DB password are set. |
| M8 | Medium | Internal error details (model repo names, operator instructions, exception text) were stored on translations and pushed to chat members; unauthenticated `/health` exposed them; `/metrics` visible to every user. | `features/messages/translation_jobs.py`, `features/system/router.py` | **Fixed**: users see generic reasons, details go to logs; `/health` hides errors in production; `METRICS_ENABLED` switch. |
| M9 | Medium | Backend container ran as root. | `backend/Dockerfile`, compose | **Fixed**: non-root user, `no-new-privileges`, `cap_drop: ALL`, unprivileged nginx, frontend port bound to 127.0.0.1. |
| L1 | Low | JWT had no issuer/audience. | `core/security.py` | **Fixed** (validated; `iat` required). |
| L2 | Low | Registration conflict said *which* field (email) was taken. | `features/auth/service.py` | **Fixed** (generic). Still inherent: a 409 reveals "username or email" exists; full fix needs email verification. |
| L3 | Low | Profile images accepted `http://` and any host; images leaked the viewer's page via Referer. | `features/users/schemas.py`, `Avatar.tsx` | **Fixed**: https only, `referrerPolicy="no-referrer"`. Remaining: the image host still sees viewers' IPs (use an image proxy to remove). |
| L4 | Low | Cookie endpoints relied only on SameSite=Strict for CSRF. | `features/auth/router.py` | **Fixed**: Origin allow-list check on refresh/logout (defence in depth). |
| L5 | Low | Rate-limiter keys never purged (memory growth with many IPs/logins). | `core/rate_limit.py` | **Fixed** (periodic purge). |
| L6 | Low | WS ticket visible in server request logs. | `core/logging.py` | **Fixed** (redaction filter). Tickets were already single-use / 30 s. |
| L7 | Low | `assert` in production code (bandit B101). | `features/conversations/service.py` | **Fixed**. |
| L8 | Low | No Python lockfile (non-reproducible installs). | `backend/` | **Fixed**: `requirements.lock`. |
| L9 | Low | Access tokens stay valid until expiry (30 min) after logout; already-open WebSockets survive logout (but not account deletion). | auth | **Open** — see recommendations. |
| L10 | Low | Local `.env` uses a 4-character database password (changed by hand from the generated one). | `backend/.env` (not in VCS) | **Open** — rotate it (below). |
| L11 | Info | No email verification or password reset exists, so registrations can use any email address. | auth | **Open**: by design for now; implement before public launch. |
| L12 | Info | Google Fonts are loaded from Google (third-party request, viewer IP visible to Google). | `index.html` | **Open**: self-host the font if this matters. |

### Verified as sound (no change needed)

- **Injection:** ORM queries only; LIKE wildcards escaped; no raw SQL besides `SELECT 1`; tested with
  injection-style input.
- **Access control:** every conversation/message/translation operation checks membership server-side,
  REST and WS; non-members get 404 (no ID probing); sender is always the authenticated user; WS payloads
  `extra=forbid`; REST schemas ignore unknown fields (mass assignment tested).
- **Delivery:** events are only addressed to explicit member IDs (no broadcast path); presence goes to
  contacts only.
- **Races and idempotency:** idempotent sends (unique `sender_id, client_message_id`), unique direct
  conversations, row-locked refresh rotation.
- **Passwords:** Argon2id (argon2-cffi defaults: 64 MiB, t=3, p=4) with timing equalisation for unknown
  users.
- **Browser storage:** access token in memory only; refresh token in an `HttpOnly`, `SameSite=Strict`,
  path-scoped cookie (`Secure` enforced in production).
- **XSS:** React escaping only, no `dangerouslySetInnerHTML`/`innerHTML`/`eval`; translation output is
  treated as text; no user-controlled links or redirects.
- **Translation input:** message content never reaches a third-party service (local inference); language
  codes validated against the enabled list; model IDs come only from server config.

## Tools run and results

| Tool | Scope | Result |
|---|---|---|
| `pip-audit` | backend virtualenv | setuptools 79 (sdist-build only) → upgraded to 84. transformers 4.57.6: 9 advisories, all requiring an attacker-controlled model/repo or unused features (Trainer, X-CLIP, LightGlue, `save_pretrained`, custom generate). Fixes need transformers 5.x, which breaks IndicTransToolkit → **accepted risk**, mitigated by H2 pinning. torch (+cpu build) not auditable from PyPI. |
| `npm audit` | frontend, all deps incl. dev | 0 vulnerabilities |
| `bandit -r app` | backend app | 0 issues (after fixes), 0 `nosec` suppressions |
| `ruff`, `oxlint`, `tsc --strict` | both apps | clean |
| Secret scan (regex for HF/AWS/JWT/private keys + real `.env` values) | whole project, excluding `node_modules`, `.venv` | no secrets outside `backend/.env` (mode 600, git-ignored) |
| Security regression tests | `tests/unit/test_security_config.py` (22), `tests/integration/test_security.py` (19) | all pass |
| CSP check | production build served with the nginx CSP, driven in Chrome | 0 violations; WebSocket, fonts, emoji picker work |

Limitations: Docker and nginx are not installed on the audit machine, so the Dockerfiles/compose/nginx config
were reviewed but not executed (the CSP itself was tested). No DAST/fuzzing tool was run. Single-process
in-memory rate limits reset on restart and are per-process.

## Required actions for you

1. **Rotate the local DB password** (L10): set a long random password in `backend/.env`, then re-run
   `bash backend/scripts/create_database.sh` (it updates the role's password).
2. Before any deployment: set the production block of `.env.example` (the app refuses to start otherwise),
   put TLS in front of nginx, set `METRICS_ENABLED=false`, keep `HF_TOKEN` out of files (use the platform's
   secret store), and consider `HF_HUB_OFFLINE=1` after the first model download.
3. When upgrading models, review the upstream diff of `modeling_indictrans.py`/`tokenization_indictrans.py`,
   then update the `*_MODEL_REVISION` values deliberately.

## Recommended next steps

- L9: bind access tokens and WS tickets to a refresh-token family (`sid` claim) so logout revokes that
  device's access token and closes its sockets; shorten `ACCESS_TOKEN_EXPIRE_MINUTES` to 15.
- Email verification + password reset (single-use, hashed, 15-minute tokens; generic responses).
- Move rate limits/tickets to Redis before running more than one backend process.
- Add a DAST pass (e.g. OWASP ZAP baseline) against a staging deployment.
- Use a separate DB role for migrations (owner) and the app (DML only).

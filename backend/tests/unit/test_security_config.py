"""Security-relevant configuration, token validation and helpers (no database)."""

import asyncio
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthError
from app.core.logging import RedactTicketsFilter
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import create_access_token, decode_access_token
from app.features.translation.service import TranslationService, public_error_message
from app.integrations.translation.base import ModelUnavailableError, TranslationError, TranslationQueueFullError

GOOD_SECRET = secrets.token_urlsafe(48)
PROD = {
    "APP_ENV": "production", "JWT_SECRET_KEY": GOOD_SECRET, "COOKIE_SECURE": True,
    "FRONTEND_ORIGIN": "https://chat.example.org", "ALLOWED_HOSTS": "chat.example.org",
    "DATABASE_URL": "postgresql+asyncpg://app:Str0ng-Pass-9x@db:5432/chat",
}


# ---------------------------------------------------------------- H1: signing key
@pytest.mark.parametrize("secret", [
    "replace_with_a_secure_random_secret_at_least_32_chars",  # the published .env.example value
    "change_me_change_me_change_me_change_me",
    "a" * 40,  # long but no entropy
    "short",
])
def test_weak_or_placeholder_jwt_secret_is_rejected(secret: str) -> None:
    with pytest.raises(ValueError):
        Settings(JWT_SECRET_KEY=secret, _env_file=None)


def test_random_jwt_secret_is_accepted() -> None:
    Settings(JWT_SECRET_KEY=GOOD_SECRET, _env_file=None)


# ---------------------------------------------------------------- M7: production safety
def test_safe_production_config_starts() -> None:
    Settings(**PROD, _env_file=None)


@pytest.mark.parametrize("override", [
    {"COOKIE_SECURE": False},
    {"FRONTEND_ORIGIN": "http://chat.example.org"},
    {"ALLOWED_HOSTS": "*"},
    {"DATABASE_URL": "postgresql+asyncpg://app_user:change_me@db/chat"},
])
def test_unsafe_production_config_refuses_to_start(override: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(**(PROD | override), _env_file=None)


# ---------------------------------------------------------------- H2: pinned model code
def test_default_checkpoints_are_pinned_to_commits() -> None:
    s = get_settings()
    for model in (s.INDIC_INDIC_MODEL, s.EN_INDIC_MODEL, s.INDIC_EN_MODEL):
        revision = s.model_revision(model)
        assert revision and len(revision) == 40 and all(c in "0123456789abcdef" for c in revision)
    assert s.model_revision("someone/else") is None


# ---------------------------------------------------------------- L1: JWT validation
def _forge(**claims: object) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": str(uuid.uuid4()), "type": "access", "iat": now, "exp": now + timedelta(minutes=5),
               "iss": s.JWT_ISSUER, "aud": s.JWT_AUDIENCE} | claims
    return jwt.encode({k: v for k, v in payload.items() if v is not None}, s.JWT_SECRET_KEY, algorithm="HS256")


def test_valid_token_round_trips() -> None:
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id)
    assert decode_access_token(token) == user_id


@pytest.mark.parametrize("token_factory", [
    lambda: _forge(aud="some-other-service"),
    lambda: _forge(iss="evil-issuer"),
    lambda: _forge(iss=None),
    lambda: _forge(type="refresh"),
    lambda: jwt.encode({"sub": str(uuid.uuid4()), "type": "access"}, "x" * 48, algorithm="HS256"),  # wrong key
    lambda: jwt.encode({"sub": str(uuid.uuid4()), "type": "access", "exp": 9999999999}, None, algorithm="none"),
])
def test_tampered_tokens_are_rejected(token_factory) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(AuthError):
        decode_access_token(token_factory())


# ---------------------------------------------------------------- helpers
def test_rate_limiter_forgets_idle_keys() -> None:
    import time

    limiter = SlidingWindowLimiter(limit=5, window_seconds=0.05)
    for i in range(SlidingWindowLimiter._PURGE_EVERY - 1):
        limiter.allow(f"ip-{i}")
    assert len(limiter) == SlidingWindowLimiter._PURGE_EVERY - 1
    time.sleep(0.1)  # every key is now idle
    limiter.allow("trigger-purge")
    assert len(limiter) == 1  # idle keys dropped instead of growing forever


def test_ws_ticket_is_redacted_from_logs() -> None:
    record = logging.LogRecord("uvicorn.error", logging.INFO, "", 0, '%s - "WebSocket %s" %s',
                               ("127.0.0.1", "/ws/chat?ticket=SECRET123abc", 403), None)
    RedactTicketsFilter().filter(record)
    assert "SECRET123abc" not in record.getMessage()
    assert "ticket=[redacted]" in record.getMessage()


def test_translation_errors_shown_to_users_hide_internal_details() -> None:
    leak = ModelUnavailableError("Access to ai4bharat/indictrans2-x is gated. Run `hf auth login` /home/x/.cache")
    message = public_error_message(leak)
    assert "ai4bharat" not in message and "hf auth" not in message and "/home" not in message
    assert public_error_message(TranslationError("Mock boom: Traceback ...")) == "Translation failed"


def test_adhoc_requests_cannot_take_the_whole_queue() -> None:
    class Slow:
        def load(self, d):  # type: ignore[no-untyped-def]
            ...

        def status(self):  # type: ignore[no-untyped-def]
            return {}

        def translate_batch(self, texts, src, tgt, d):  # type: ignore[no-untyped-def]
            import time
            time.sleep(0.2)
            return [f"ok:{t}" for t in texts]

    svc = TranslationService(get_settings().model_copy(update={"TRANSLATION_MAX_QUEUE_SIZE": 4}), Slow())

    async def go() -> None:
        previews = [asyncio.create_task(svc.translate(f"p{i}", "guj_Gujr", "hin_Deva", adhoc=True)) for i in range(2)]
        await asyncio.sleep(0.01)
        with pytest.raises(TranslationQueueFullError):  # previews capped at half the queue
            await svc.translate("p3", "guj_Gujr", "hin_Deva", adhoc=True)
        result = await svc.translate("real message", "guj_Gujr", "hin_Deva")  # real messages still fit
        assert result.text == "ok:real message"
        await asyncio.gather(*previews)

    asyncio.run(go())

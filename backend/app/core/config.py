"""Application settings loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDER_WORDS = ("replace", "change_me", "changeme", "example", "placeholder", "your_secret", "secret_key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://app_user:change_me@localhost:5432/multilingual_chat"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_ECHO: bool = False

    JWT_SECRET_KEY: str = Field(default="", min_length=0)
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "multilingual-chat"
    JWT_AUDIENCE: str = "multilingual-chat-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    REFRESH_COOKIE_NAME: str = "mlchat_refresh"
    COOKIE_SECURE: bool = False

    # Comma-separated list of allowed browser origins (CORS + WebSocket Origin check).
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    # Comma-separated Host header allow-list (TrustedHostMiddleware). "*" only outside production.
    ALLOWED_HOSTS: str = "*"
    # Reject request bodies larger than this (JSON APIs only; no uploads).
    MAX_REQUEST_BODY_BYTES: int = 65_536
    # /api/v1/metrics exposes operational counters; keep it off in production unless protected upstream.
    METRICS_ENABLED: bool = True

    # WebSocket
    WS_TICKET_EXPIRE_SECONDS: int = 30
    WS_IDLE_TIMEOUT_SECONDS: int = 60
    WS_MAX_MESSAGE_BYTES: int = 16_384
    WS_SEND_QUEUE_SIZE: int = 256
    WS_MESSAGES_PER_10S: int = 20  # message.send per user (all connections combined)
    WS_EVENTS_PER_10S: int = 60  # any event per connection (typing, read, ping, ...)
    WS_MAX_CONNECTIONS_PER_USER: int = 5
    WS_TICKETS_PER_MINUTE: int = 20

    # Messaging
    MAX_MESSAGE_LENGTH: int = 2000

    # Rate limiting for auth endpoints (per client IP)
    AUTH_RATE_LIMIT_PER_MINUTE: int = 10
    # Login attempts per account (any IP) per 15 minutes: slows distributed password guessing.
    LOGIN_ATTEMPTS_PER_ACCOUNT_15MIN: int = 20
    # POST /translations (composer live preview + ad-hoc), per user
    TRANSLATE_RATE_LIMIT_PER_MINUTE: int = 60

    # Languages: comma-separated IndicTrans2 codes enabled in this deployment.
    SUPPORTED_LANGUAGES: str = (
        "eng_Latn,guj_Gujr,hin_Deva,tam_Taml,ben_Beng,mar_Deva,tel_Telu,"
        "kan_Knda,mal_Mlym,pan_Guru,ory_Orya,asm_Beng"
    )

    # Translation
    TRANSLATION_BACKEND: Literal["indictrans2", "mock", "disabled"] = "indictrans2"
    TRANSLATION_DEVICE: Literal["cpu"] = "cpu"
    TRANSLATION_MAX_CONCURRENT_JOBS: int = 1
    TRANSLATION_MAX_QUEUE_SIZE: int = 50
    TRANSLATION_TIMEOUT_SECONDS: float = 120.0
    TRANSLATION_PRELOAD: bool = True
    TRANSLATION_TORCH_THREADS: int = 4
    TRANSLATION_NUM_BEAMS: int = 3
    TRANSLATION_MAX_NEW_TOKENS: int = 256
    # IndicTrans2's remote modeling code indexes past_key_values as legacy tuples, which crashes
    # with transformers 4.5x cache objects (AttributeError: 'NoneType' has no attribute 'shape').
    # Disabling the KV cache avoids it; costs speed only on long outputs.
    TRANSLATION_USE_CACHE: bool = False
    # Guards against degenerate repetition on short/odd input (e.g. "hii hindi" -> "हिहिहि…").
    TRANSLATION_REPETITION_PENALTY: float = 1.2
    TRANSLATION_NO_REPEAT_NGRAM_SIZE: int = 3
    TRANSLATION_CACHE_SIZE: int = 1000
    # Ad-hoc/preview requests may use at most this share of the queue, so they can never starve
    # translations of real messages.
    TRANSLATION_ADHOC_QUEUE_SHARE: float = 0.5
    INDIC_INDIC_MODEL: str = "ai4bharat/indictrans2-indic-indic-dist-320M"
    EN_INDIC_MODEL: str = "ai4bharat/indictrans2-en-indic-dist-200M"
    INDIC_EN_MODEL: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    # The checkpoints ship Python code (trust_remote_code); pinning exact commits means a change
    # upstream can never silently run new code here. Update deliberately after reviewing the diff.
    INDIC_INDIC_MODEL_REVISION: str = "ffb7582b6d43791f1fb26b2153fc065f2e9ea575"
    EN_INDIC_MODEL_REVISION: str = "2cfd0a20057756d756bf3e53528f492afc52f91a"
    INDIC_EN_MODEL_REVISION: str = "d66a2122ad6d28184f3dc3797b652bd80ae3f65f"
    # Mock backend only: artificial latency in seconds.
    MOCK_TRANSLATION_DELAY: float = 0.0

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _secret_required(cls, v: str) -> str:
        """Reject empty, short, placeholder or low-entropy signing keys (a known key = forgeable logins)."""
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be set to a random string of at least 32 characters")
        lowered = v.lower()
        if any(word in lowered for word in _PLACEHOLDER_WORDS) or len(set(v)) < 16:
            raise ValueError("JWT_SECRET_KEY looks like a placeholder; generate one with "
                             "python3 -c \"import secrets; print(secrets.token_urlsafe(48))\"")
        return v

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        """Refuse to start in production with development-grade settings."""
        if self.APP_ENV != "production":
            return self
        problems = []
        if not self.COOKIE_SECURE:
            problems.append("COOKIE_SECURE must be true (HTTPS)")
        if any(urlsplit(o).scheme != "https" for o in self.allowed_origins):
            problems.append("FRONTEND_ORIGIN must list only https:// origins")
        if "*" in self.allowed_hosts:
            problems.append("ALLOWED_HOSTS must list the real host names")
        if any(word in self.DATABASE_URL.lower() for word in _PLACEHOLDER_WORDS):
            problems.append("DATABASE_URL still contains a placeholder password")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def allowed_hosts(self) -> list[str]:
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]

    def model_revision(self, model_name: str) -> str | None:
        """Pinned commit for a configured checkpoint (None = unpinned custom model)."""
        return {
            self.INDIC_INDIC_MODEL: self.INDIC_INDIC_MODEL_REVISION,
            self.EN_INDIC_MODEL: self.EN_INDIC_MODEL_REVISION,
            self.INDIC_EN_MODEL: self.INDIC_EN_MODEL_REVISION,
        }.get(model_name) or None

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.FRONTEND_ORIGIN.split(",") if o.strip()]

    @property
    def enabled_languages(self) -> list[str]:
        return [c.strip() for c in self.SUPPORTED_LANGUAGES.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

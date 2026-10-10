"""Test environment shared by unit and integration tests.

Unit tests need no database. Integration tests (tests/integration) need TEST_DATABASE_URL pointing at
a disposable PostgreSQL database (it is wiped). Translation uses the mock engine; nothing is downloaded.
"""

import os
import secrets

os.environ.update({
    "APP_ENV": "test",
    "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY") or secrets.token_urlsafe(48),
    "TRANSLATION_BACKEND": os.environ.get("TEST_TRANSLATION_BACKEND", "mock"),
    "FRONTEND_ORIGIN": "http://localhost:5173",
    "AUTH_RATE_LIMIT_PER_MINUTE": "1000",
    "LOG_LEVEL": "WARNING",
})
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

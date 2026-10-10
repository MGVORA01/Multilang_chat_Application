"""Password hashing (Argon2id) and JWT / opaque token helpers."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.exceptions import AuthError

_hasher = PasswordHasher()
# Used to equalize timing when the user does not exist.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    expires_in = s.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iss": s.JWT_ISSUER,
        "aud": s.JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM), expires_in


def decode_access_token(token: str) -> uuid.UUID:
    s = get_settings()
    try:
        # Pinned algorithm list (no "none"/alg confusion) plus issuer and audience checks.
        payload = jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM],
                             issuer=s.JWT_ISSUER, audience=s.JWT_AUDIENCE,
                             options={"require": ["exp", "iat", "sub", "type", "iss", "aud"]})
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Access token expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid access token", code="invalid_token") from exc
    if payload.get("type") != "access":
        raise AuthError("Invalid access token", code="invalid_token")
    try:
        return uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise AuthError("Invalid access token", code="invalid_token") from exc


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

"""Registration, login and rotating refresh-token sessions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AuthError, ConflictError, RateLimitedError
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import create_access_token, hash_password, hash_token, new_opaque_token, verify_password
from app.features.auth import repository as token_repo
from app.features.auth.schemas import RegisterRequest
from app.features.users import repository as user_repo
from app.features.users.models import User


@dataclass(frozen=True)
class IssuedSession:
    """Tokens for a freshly authenticated user. The refresh token goes in an httpOnly cookie."""

    user: User
    access_token: str
    expires_in: int
    refresh_token: str


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings,
                 login_limiter: SlidingWindowLimiter | None = None) -> None:
        self.session = session
        self.settings = settings
        self.login_limiter = login_limiter

    async def register(self, body: RegisterRequest) -> IssuedSession:
        """Create an account and sign it in; raises ConflictError if username/email is taken."""
        username_taken, email_taken = await user_repo.exists_username_or_email(
            self.session, body.username, body.email
        )
        if username_taken or email_taken:
            # Deliberately not saying which one, so registration can't be used to test emails.
            raise ConflictError("Username or email already registered", code="user_exists")
        user = User(username=body.username, email=body.email, password_hash=hash_password(body.password),
                    display_name=body.display_name, preferred_language=body.preferred_language)
        user_repo.add(self.session, user)
        try:
            await self.session.flush()
        except IntegrityError as exc:  # lost a race with a concurrent registration
            await self.session.rollback()
            raise ConflictError("Username or email already registered", code="user_exists") from exc
        await self.session.refresh(user)
        return await self._issue(user)

    async def login(self, login: str, password: str) -> IssuedSession:
        # Per-account budget on top of the per-IP limit: slows password guessing spread over many IPs.
        if self.login_limiter is not None and not self.login_limiter.allow(login.strip().lower()):
            raise RateLimitedError("Too many login attempts for this account, try again later")
        user = await user_repo.get_by_login(self.session, login)
        # verify_password runs even for unknown users so timing doesn't reveal which logins exist.
        if not verify_password(password, user.password_hash if user else None) or user is None:
            raise AuthError("Invalid username/email or password", code="invalid_credentials")
        if not user.is_active:
            raise AuthError("Account is disabled", code="account_disabled")
        return await self._issue(user)

    async def refresh(self, raw_token: str | None) -> IssuedSession:
        """Rotate a refresh token: the presented token is revoked and a new pair issued."""
        if not raw_token:
            raise AuthError("No refresh token", code="refresh_missing")
        record = await token_repo.get_refresh_token_for_update(self.session, hash_token(raw_token))
        now = datetime.now(UTC)
        if record is not None and record.revoked_at is not None:
            # A rotated token was presented again: it was copied. Revoke every session of this user,
            # so whichever party (owner or thief) holds the newer token must log in again.
            await token_repo.revoke_all_for_user(self.session, record.user_id, now)
            await self.session.commit()
            raise AuthError("Refresh token reuse detected; please sign in again", code="refresh_reused")
        if record is None or record.expires_at < now:
            raise AuthError("Refresh token invalid or expired", code="refresh_invalid")
        user = await user_repo.get_active_by_id(self.session, record.user_id)
        if user is None:
            raise AuthError("User not found or inactive", code="refresh_invalid")
        record.revoked_at = now
        return await self._issue(user)

    async def logout(self, raw_token: str | None) -> None:
        """Revoke the presented refresh token (idempotent)."""
        if not raw_token:
            return
        record = await token_repo.get_refresh_token_for_update(self.session, hash_token(raw_token))
        if record is not None and record.revoked_at is None:
            record.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def _issue(self, user: User) -> IssuedSession:
        refresh = new_opaque_token()
        token_repo.add_refresh_token(
            self.session, user.id, hash_token(refresh),
            datetime.now(UTC) + timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.session.commit()
        access, expires_in = create_access_token(user.id)
        return IssuedSession(user=user, access_token=access, expires_in=expires_in, refresh_token=refresh)

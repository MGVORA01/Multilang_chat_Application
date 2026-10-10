"""Authentication dependencies: resolve the current user from the Bearer token."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import SessionDep
from app.core.exceptions import AuthError
from app.core.security import decode_access_token
from app.features.users import repository as user_repo
from app.features.users.models import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Return the active user for a valid access token, or raise 401."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthError("Not authenticated", code="not_authenticated")
    user_id = decode_access_token(credentials.credentials)
    user = await user_repo.get_active_by_id(session, user_id)
    if user is None:
        raise AuthError("User not found or inactive", code="invalid_token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

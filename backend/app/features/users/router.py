"""User endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import ManagerDep, SessionDep, auth_rate_limit
from app.features.auth.dependencies import CurrentUser
from app.features.auth.router import clear_refresh_cookie
from app.features.users.schemas import (
    DeleteAccountRequest,
    UpdateLanguageRequest,
    UpdateProfileRequest,
    UserMe,
    UserPublic,
)
from app.features.users.service import UserService
from app.shared.schemas import Page

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(session: SessionDep, manager: ManagerDep) -> UserService:
    return UserService(session, manager)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


@router.get("", response_model=Page[UserPublic])
async def search_users(
    user: CurrentUser, users: UserServiceDep,
    q: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[UserPublic]:
    items, total = await users.search(q, user.id, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.patch("/me", response_model=UserMe)
async def update_me(body: UpdateProfileRequest, user: CurrentUser, users: UserServiceDep) -> UserMe:
    return UserMe.model_validate(await users.update_profile(user, body))


@router.patch("/me/language", response_model=UserMe)
async def update_language(body: UpdateLanguageRequest, user: CurrentUser, users: UserServiceDep) -> UserMe:
    return UserMe.model_validate(await users.update_language(user, body.preferred_language))


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(auth_rate_limit)])
async def delete_me(body: DeleteAccountRequest, user: CurrentUser, users: UserServiceDep) -> Response:
    """Permanently delete the account and all its conversations. Requires the password."""
    await users.delete_account(user, body.password)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: uuid.UUID, user: CurrentUser, users: UserServiceDep) -> UserPublic:
    return await users.get_public(user.id, user_id)

"""User search, profile/language updates and account deletion."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import verify_password
from app.features.conversations import repository as conv_repo
from app.features.users import repository as user_repo
from app.features.users.models import User
from app.features.users.schemas import UpdateProfileRequest, UserPublic
from app.features.users.serializers import user_public
from app.websocket.manager import ConnectionManager
from app.websocket.protocol import CloseCode, ServerEvent, server_event

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: AsyncSession, manager: ConnectionManager) -> None:
        self.session = session
        self.manager = manager

    async def search(self, query: str | None, viewer_id: uuid.UUID, limit: int,
                     offset: int) -> tuple[list[UserPublic], int]:
        rows, total = await user_repo.search(self.session, query, viewer_id, limit, offset)
        contacts = await conv_repo.contact_ids(self.session, viewer_id)
        return [user_public(u, self.manager, reveal_presence=u.id in contacts) for u in rows], total

    async def get_public(self, viewer_id: uuid.UUID, user_id: uuid.UUID) -> UserPublic:
        user = await user_repo.get_active_by_id(self.session, user_id)
        if user is None:
            raise NotFoundError("User not found", code="user_not_found")
        contacts = await conv_repo.contact_ids(self.session, viewer_id)
        return user_public(user, self.manager, reveal_presence=user.id in contacts)

    async def update_profile(self, user: User, body: UpdateProfileRequest) -> User:
        if body.display_name is not None:
            user.display_name = body.display_name.strip()
        if "profile_image_url" in body.model_fields_set:
            user.profile_image_url = str(body.profile_image_url) if body.profile_image_url else None
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_language(self, user: User, language: str) -> User:
        """Applies to future deliveries only; existing translations are not rewritten."""
        user.preferred_language = language
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_account(self, user: User, password: str) -> None:
        """Hard-delete the account and every direct conversation it was part of.

        Other participants receive `conversation.removed`; the user's sockets are closed (4410).
        """
        if not verify_password(password, user.password_hash):
            raise ForbiddenError("Incorrect password", code="invalid_password")
        user_id = user.id
        audience = await conv_repo.direct_conversations_with_others(self.session, user_id)
        await conv_repo.delete_many(self.session, list(audience))
        await user_repo.delete(self.session, user_id)
        await self.session.commit()
        logger.info("account deleted", extra={"user_id": str(user_id), "conversations": len(audience)})

        for conversation_id, members in audience.items():
            self.manager.send_to_users(members, server_event(ServerEvent.CONVERSATION_REMOVED, {
                "conversation_id": str(conversation_id), "reason": "account_deleted",
            }))
        await self.manager.disconnect_user(user_id, CloseCode.ACCOUNT_DELETED, "account deleted")

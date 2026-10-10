"""Conversation listing, direct-conversation creation and membership checks."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.features.conversations import repository as conv_repo
from app.features.conversations.models import Conversation, ConversationMember, ConversationType
from app.features.conversations.schemas import ConversationOut
from app.features.conversations.serializers import conversation_out
from app.features.messages import repository as msg_repo
from app.features.users import repository as user_repo
from app.websocket.manager import ConnectionManager


async def require_membership(session: AsyncSession, conversation_id: uuid.UUID,
                             user_id: uuid.UUID) -> Conversation:
    """Return the conversation if `user_id` is a member; otherwise 404.

    "Not found" and "not a member" share one error so conversation IDs cannot be probed.
    """
    conversation = await conv_repo.get(session, conversation_id)
    if conversation is None or not any(m.user_id == user_id for m in conversation.members):
        raise NotFoundError("Conversation not found", code="conversation_not_found")
    return conversation


class ConversationService:
    def __init__(self, session: AsyncSession, manager: ConnectionManager) -> None:
        self.session = session
        self.manager = manager

    async def list_for_user(self, user_id: uuid.UUID, limit: int, offset: int) -> tuple[list[ConversationOut], int]:
        rows, total = await conv_repo.list_for_user(self.session, user_id, limit, offset)
        unread = await conv_repo.unread_counts(self.session, user_id, [c.id for c in rows])
        items = [await self._out(c, unread.get(c.id, 0)) for c in rows]
        return items, total

    async def get(self, user_id: uuid.UUID, conversation_id: uuid.UUID) -> ConversationOut:
        conversation = await require_membership(self.session, conversation_id, user_id)
        unread = await conv_repo.unread_counts(self.session, user_id, [conversation_id])
        return await self._out(conversation, unread.get(conversation_id, 0))

    async def get_or_create_direct(self, user_id: uuid.UUID,
                                   participant_id: uuid.UUID) -> tuple[ConversationOut, bool]:
        """Return (conversation, created). Two users never get two direct conversations."""
        if participant_id == user_id:
            raise AppError("You cannot start a conversation with yourself", code="invalid_participant")
        other = await user_repo.get_active_by_id(self.session, participant_id)
        if other is None:
            raise NotFoundError("User not found", code="user_not_found")

        key = conv_repo.direct_key(user_id, other.id)
        existing = await conv_repo.get_by_direct_key(self.session, key)
        if existing is None:
            conversation = Conversation(conversation_type=ConversationType.DIRECT, direct_key=key)
            conversation.members = [ConversationMember(user_id=user_id), ConversationMember(user_id=other.id)]
            conv_repo.add(self.session, conversation)
            try:
                await self.session.commit()
            except IntegrityError:
                # Both users pressed "Message" at the same time; the unique direct_key picked a winner.
                await self.session.rollback()
                existing = await conv_repo.get_by_direct_key(self.session, key)
                if existing is None:
                    raise
            else:
                new_id = conversation.id
                self.session.expunge_all()  # reload so members' users are eagerly loaded
                created = await conv_repo.get(self.session, new_id)
                if created is None:  # pragma: no cover - would mean the commit silently failed
                    raise RuntimeError("Conversation vanished right after creation")
                return conversation_out(created, self.manager), True

        unread = await conv_repo.unread_counts(self.session, user_id, [existing.id])
        return await self._out(existing, unread.get(existing.id, 0)), False

    async def _out(self, conversation: Conversation, unread: int) -> ConversationOut:
        last = await msg_repo.last_message(self.session, conversation.id)
        return conversation_out(conversation, self.manager, last, unread)

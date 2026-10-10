"""Persistence for conversations and memberships."""

import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conversations.models import Conversation, ConversationMember, ConversationType
from app.features.messages.models import Message, MessageReceipt


def direct_key(a: uuid.UUID, b: uuid.UUID) -> str:
    x, y = sorted([str(a), str(b)])
    return f"{x}:{y}"


async def get(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


async def get_by_direct_key(session: AsyncSession, key: str) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.direct_key == key)
    return (await session.execute(stmt)).scalar_one_or_none()


async def is_member(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = select(ConversationMember.user_id).where(
        ConversationMember.conversation_id == conversation_id, ConversationMember.user_id == user_id
    )
    return (await session.execute(stmt)).first() is not None


async def member_ids(session: AsyncSession, conversation_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(ConversationMember.user_id).where(ConversationMember.conversation_id == conversation_id)
    return list((await session.execute(stmt)).scalars().all())


async def contact_ids(session: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Users sharing at least one conversation with `user_id` (presence audience)."""
    mine = select(ConversationMember.conversation_id).where(ConversationMember.user_id == user_id)
    stmt = select(ConversationMember.user_id).where(
        ConversationMember.conversation_id.in_(mine), ConversationMember.user_id != user_id
    ).distinct()
    return set((await session.execute(stmt)).scalars().all())


async def list_for_user(session: AsyncSession, user_id: uuid.UUID, limit: int,
                        offset: int) -> tuple[list[Conversation], int]:
    mine = select(ConversationMember.conversation_id).where(ConversationMember.user_id == user_id)
    total = (await session.execute(
        select(func.count()).select_from(Conversation).where(Conversation.id.in_(mine))
    )).scalar_one()
    stmt = (
        select(Conversation)
        .where(Conversation.id.in_(mine))
        .order_by(func.coalesce(Conversation.last_message_at, Conversation.created_at).desc(), Conversation.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all()), total


async def unread_counts(session: AsyncSession, user_id: uuid.UUID,
                        conversation_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not conversation_ids:
        return {}
    stmt = (
        select(Message.conversation_id, func.count())
        .join(MessageReceipt, MessageReceipt.message_id == Message.id)
        .where(MessageReceipt.user_id == user_id, MessageReceipt.read_at.is_(None),
               Message.conversation_id.in_(conversation_ids), Message.deleted_at.is_(None))
        .group_by(Message.conversation_id)
    )
    return {cid: n for cid, n in (await session.execute(stmt)).all()}


def add(session: AsyncSession, conversation: Conversation) -> None:
    session.add(conversation)


async def set_last_read(session: AsyncSession, conversation_id: uuid.UUID, user_id: uuid.UUID,
                        message_id: uuid.UUID) -> None:
    await session.execute(
        update(ConversationMember)
        .where(ConversationMember.conversation_id == conversation_id, ConversationMember.user_id == user_id)
        .values(last_read_message_id=message_id)
    )


async def direct_conversations_with_others(session: AsyncSession,
                                           user_id: uuid.UUID) -> dict[uuid.UUID, list[uuid.UUID]]:
    """{conversation_id: [other member ids]} for every direct conversation of `user_id`."""
    mine = select(ConversationMember.conversation_id).where(ConversationMember.user_id == user_id)
    direct_ids = list((await session.execute(
        select(Conversation.id).where(Conversation.id.in_(mine),
                                      Conversation.conversation_type == ConversationType.DIRECT)
    )).scalars().all())
    result: dict[uuid.UUID, list[uuid.UUID]] = {cid: [] for cid in direct_ids}
    if direct_ids:
        rows = (await session.execute(
            select(ConversationMember.conversation_id, ConversationMember.user_id)
            .where(ConversationMember.conversation_id.in_(direct_ids), ConversationMember.user_id != user_id)
        )).all()
        for conversation_id, member_id in rows:
            result[conversation_id].append(member_id)
    return result


async def delete_many(session: AsyncSession, conversation_ids: list[uuid.UUID]) -> None:
    """Cascades to members, messages, translations and receipts."""
    if conversation_ids:
        await session.execute(delete(Conversation).where(Conversation.id.in_(conversation_ids)))

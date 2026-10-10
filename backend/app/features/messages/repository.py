"""Persistence for messages, translations and receipts."""

import uuid
from datetime import datetime

from sqlalchemy import and_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.messages.models import Message, MessageReceipt, MessageTranslation, TranslationStatus


async def get(session: AsyncSession, message_id: uuid.UUID) -> Message | None:
    return await session.get(Message, message_id)


async def get_by_client_id(session: AsyncSession, sender_id: uuid.UUID, client_message_id: str) -> Message | None:
    stmt = select(Message).where(Message.sender_id == sender_id, Message.client_message_id == client_message_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def history(session: AsyncSession, conversation_id: uuid.UUID, limit: int,
                  before: Message | None) -> tuple[list[Message], bool]:
    """Newest-first page of messages older than `before`; returns (oldest-first list, has_more)."""
    conditions = [Message.conversation_id == conversation_id, Message.deleted_at.is_(None)]
    if before is not None:
        conditions.append(tuple_(Message.created_at, Message.id) < tuple_(before.created_at, before.id))
    stmt = (
        select(Message).where(*conditions)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit + 1)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    rows.reverse()
    return rows, has_more


async def last_message(session: AsyncSession, conversation_id: uuid.UUID) -> Message | None:
    stmt = (
        select(Message).where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_translation(session: AsyncSession, translation_id: uuid.UUID) -> MessageTranslation | None:
    return await session.get(MessageTranslation, translation_id)


async def get_translation_for(session: AsyncSession, message_id: uuid.UUID,
                              target_language: str) -> MessageTranslation | None:
    stmt = select(MessageTranslation).where(
        MessageTranslation.message_id == message_id, MessageTranslation.target_language == target_language
    ).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def mark_delivered(session: AsyncSession, user_id: uuid.UUID, message_ids: list[uuid.UUID],
                         when: datetime) -> list[uuid.UUID]:
    if not message_ids:
        return []
    stmt = (
        update(MessageReceipt)
        .where(MessageReceipt.user_id == user_id, MessageReceipt.message_id.in_(message_ids),
               MessageReceipt.delivered_at.is_(None))
        .values(delivered_at=when)
        .returning(MessageReceipt.message_id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_read_up_to(session: AsyncSession, user_id: uuid.UUID, up_to: Message,
                          when: datetime) -> list[uuid.UUID]:
    """Mark every unread message in `up_to`'s conversation, up to and including it, as read."""
    older_or_equal = select(Message.id).where(
        Message.conversation_id == up_to.conversation_id,
        tuple_(Message.created_at, Message.id) <= tuple_(up_to.created_at, up_to.id),
    )
    stmt = (
        update(MessageReceipt)
        .where(and_(MessageReceipt.user_id == user_id, MessageReceipt.read_at.is_(None),
                    MessageReceipt.message_id.in_(older_or_equal)))
        .values(read_at=when)
        .returning(MessageReceipt.message_id)
    )
    ids = list((await session.execute(stmt)).scalars().all())
    # Reading implies delivery.
    if ids:
        await session.execute(
            update(MessageReceipt)
            .where(MessageReceipt.user_id == user_id, MessageReceipt.message_id.in_(ids),
                   MessageReceipt.delivered_at.is_(None))
            .values(delivered_at=when)
        )
    return ids


async def senders_of(session: AsyncSession, message_ids: list[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    if not message_ids:
        return {}
    rows = (await session.execute(select(Message.id, Message.sender_id).where(Message.id.in_(message_ids)))).all()
    return {mid: sid for mid, sid in rows}


async def fail_stale_pending_translations(session: AsyncSession) -> int:
    """At startup, jobs from a previous process can never finish: mark them failed (retryable)."""
    result = await session.execute(
        update(MessageTranslation)
        .where(MessageTranslation.status == TranslationStatus.PENDING)
        .values(status=TranslationStatus.FAILED,
                error_message="Translation interrupted by server restart; retry available")
    )
    return result.rowcount or 0


def add(session: AsyncSession, entity: Message | MessageReceipt | MessageTranslation) -> None:
    session.add(entity)

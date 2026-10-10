"""Conversation and membership entities."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.users.models import User


class ConversationType(StrEnum):
    DIRECT = "direct"
    GROUP = "group"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_type: Mapped[str] = mapped_column(String(16), default=ConversationType.DIRECT)
    # For direct conversations: "<smaller uuid>:<larger uuid>". Unique, so two users can
    # never end up with two direct conversations. NULL for group conversations.
    direct_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    title: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    last_message_at: Mapped[datetime | None]

    members: Mapped[list["ConversationMember"]] = relationship(
        back_populates="conversation", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("conversation_type IN ('direct', 'group')", name="type"),
        CheckConstraint(
            "(conversation_type = 'direct' AND direct_key IS NOT NULL) OR conversation_type = 'group'",
            name="direct_key",
        ),
    )


class ConversationMember(Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_read_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL", use_alter=True)
    )

    conversation: Mapped[Conversation] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(lazy="joined")

    __table_args__ = (Index("ix_conversation_members_user_id", "user_id"),)

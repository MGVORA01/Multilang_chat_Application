"""Message, per-language translation and per-recipient receipt entities."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TranslationStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_message_id: Mapped[str | None] = mapped_column(String(64))
    original_text: Mapped[str] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None]

    translations: Mapped[list["MessageTranslation"]] = relationship(
        back_populates="message", lazy="selectin", cascade="all, delete-orphan"
    )
    receipts: Mapped[list["MessageReceipt"]] = relationship(lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        # Idempotency: a client retry with the same client_message_id never creates a duplicate.
        UniqueConstraint("sender_id", "client_message_id", name="uq_messages_sender_client_message_id"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at", "id"),
    )


class MessageTranslation(Base):
    __tablename__ = "message_translations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    target_language: Mapped[str] = mapped_column(String(16))
    translated_text: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default=TranslationStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    translated_at: Mapped[datetime | None]

    message: Mapped[Message] = relationship(back_populates="translations")

    __table_args__ = (
        UniqueConstraint("message_id", "target_language", name="uq_message_translations_message_target"),
        CheckConstraint("status IN ('pending', 'completed', 'failed')", name="status"),
        CheckConstraint(
            "status <> 'completed' OR (translated_text IS NOT NULL AND length(translated_text) > 0)",
            name="completed_has_text",
        ),
        Index("ix_message_translations_status", "status"),
    )


class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    delivered_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_message_receipts_user_unread", "user_id", "read_at"),)

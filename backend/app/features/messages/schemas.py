"""Message and translation-record schemas."""

import uuid
from datetime import datetime
from typing import Literal

from app.shared.schemas import ApiModel

TranslationStatusLiteral = Literal["pending", "completed", "failed"]
DeliveryStatus = Literal["sent", "delivered", "read"]


class TranslationOut(ApiModel):
    id: uuid.UUID
    message_id: uuid.UUID
    target_language: str
    translated_text: str | None
    model_name: str | None
    status: TranslationStatusLiteral
    error_message: str | None
    translated_at: datetime | None


class MessageOut(ApiModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    client_message_id: str | None
    original_text: str
    source_language: str
    created_at: datetime
    translations: list[TranslationOut]
    # Aggregate state over all recipients (meaningful for the sender's own messages).
    status: DeliveryStatus


class RetryTranslationRequest(ApiModel):
    # Retry/create a translation for this language; defaults to the caller's preferred language.
    target_language: str | None = None

"""Conversation request/response schemas."""

import uuid
from datetime import datetime
from typing import Literal

from app.features.messages.schemas import MessageOut
from app.features.users.schemas import UserPublic
from app.shared.schemas import ApiModel


class ConversationOut(ApiModel):
    id: uuid.UUID
    conversation_type: Literal["direct", "group"]
    title: str | None
    created_at: datetime
    last_message_at: datetime | None
    members: list[UserPublic]
    last_message: MessageOut | None = None
    unread_count: int = 0


class CreateConversationRequest(ApiModel):
    participant_id: uuid.UUID

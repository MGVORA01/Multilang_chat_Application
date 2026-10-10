"""Typed WebSocket event protocol. See docs/websocket-protocol.md.

Client -> server envelope:  {"type": str, "id": str | null, "payload": object}
Server -> client envelope:  {"type": str, "id": str, "correlation_id": str | null,
                             "payload": object, "ts": ISO-8601 UTC}
"""

import uuid
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.languages import validate_language


class ClientEvent(StrEnum):
    MESSAGE_SEND = "message.send"
    MESSAGE_READ = "message.read"
    TYPING_START = "typing.start"
    TYPING_STOP = "typing.stop"
    PING = "ping"


class ServerEvent(StrEnum):
    SESSION_READY = "session.ready"
    MESSAGE_CREATED = "message.created"
    MESSAGE_TRANSLATED = "message.translated"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_READ = "message.read"
    TYPING_STARTED = "typing.started"
    TYPING_STOPPED = "typing.stopped"
    PRESENCE_UPDATED = "presence.updated"
    USER_UPDATED = "user.updated"
    CONVERSATION_REMOVED = "conversation.removed"
    ERROR = "error"
    PONG = "pong"


class CloseCode(IntEnum):
    SLOW_CLIENT = 1013
    UNAUTHORIZED = 4401
    ORIGIN_NOT_ALLOWED = 4403
    IDLE_TIMEOUT = 4408
    ACCOUNT_DELETED = 4410
    TOO_MANY_CONNECTIONS = 4429


class ClientEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=64)
    id: str | None = Field(default=None, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageSendPayload(_Payload):
    conversation_id: uuid.UUID
    text: str = Field(min_length=1)
    client_message_id: str = Field(min_length=1, max_length=64)
    # Optional; when omitted it is detected from the text's script (see features/translation/language_detection.py).
    source_language: str | None = None

    @field_validator("source_language")
    @classmethod
    def _lang(cls, v: str | None) -> str | None:
        return None if v is None else validate_language(v)


class MessageReadPayload(_Payload):
    conversation_id: uuid.UUID
    # Marks this message and every earlier message in the conversation as read.
    message_id: uuid.UUID


class TypingPayload(_Payload):
    conversation_id: uuid.UUID


class PingPayload(_Payload):
    pass


CLIENT_PAYLOADS: dict[str, type[_Payload]] = {
    ClientEvent.MESSAGE_SEND: MessageSendPayload,
    ClientEvent.MESSAGE_READ: MessageReadPayload,
    ClientEvent.TYPING_START: TypingPayload,
    ClientEvent.TYPING_STOP: TypingPayload,
    ClientEvent.PING: PingPayload,
}


def server_event(type_: ServerEvent, payload: dict[str, Any], correlation_id: str | None = None) -> dict[str, Any]:
    """Build a server -> client envelope."""
    return {
        "type": type_,
        "id": uuid.uuid4().hex,
        "correlation_id": correlation_id,
        "payload": payload,
        "ts": datetime.now(UTC).isoformat(),
    }


def error_event(code: str, message: str, correlation_id: str | None = None,
                details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    return server_event(ServerEvent.ERROR, payload, correlation_id)

"""Validate one client frame and dispatch it to the right service. Never raises: errors become
`error` events with the client's correlation id, so one bad event can't kill the socket."""

import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import ValidationError

from app.core.exceptions import AppError
from app.core.rate_limit import SlidingWindowLimiter
from app.features.messages.service import MessageService
from app.features.users.models import User
from app.integrations.translation.base import TranslationError
from app.websocket.manager import ClientConnection
from app.websocket.protocol import (
    CLIENT_PAYLOADS,
    ClientEnvelope,
    ClientEvent,
    MessageReadPayload,
    MessageSendPayload,
    ServerEvent,
    TypingPayload,
    error_event,
    server_event,
)

logger = logging.getLogger(__name__)

UserLoader = Callable[[uuid.UUID], Coroutine[Any, Any, User | None]]


def reply(conn: ClientConnection, event: dict[str, Any]) -> None:
    conn.enqueue(json.dumps(event, default=str, ensure_ascii=False))


def _errors(exc: ValidationError) -> list[dict[str, object]]:
    return [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]


class FrameHandler:
    """Per-connection dispatcher (holds the connection's send rate limiter)."""

    def __init__(self, conn: ClientConnection, user: User, messages: MessageService, load_user: UserLoader,
                 max_bytes: int, send_limiter: SlidingWindowLimiter, events_per_10s: int) -> None:
        self.conn = conn
        self.user = user
        self.messages = messages
        self.load_user = load_user
        self.max_bytes = max_bytes
        # Shared across all of the user's connections, so opening more sockets doesn't raise the limit.
        self.send_limiter = send_limiter
        # Any event type (typing, read, ping...) on this connection: each one may hit the database.
        self.event_limiter = SlidingWindowLimiter(events_per_10s, 10)

    async def handle(self, raw: str) -> None:
        if not self.event_limiter.allow("any"):
            reply(self.conn, error_event("rate_limited", "Too many events, slow down"))
            return
        if len(raw.encode()) > self.max_bytes:
            reply(self.conn, error_event("payload_too_large", f"Frame exceeds {self.max_bytes} bytes"))
            return
        try:
            envelope = ClientEnvelope.model_validate_json(raw)
        except ValidationError as exc:
            reply(self.conn, error_event("invalid_event", "Malformed event envelope", details=_errors(exc)))
            return
        cid = envelope.id
        model = CLIENT_PAYLOADS.get(envelope.type)
        if model is None:
            reply(self.conn, error_event("unknown_event", f"Unknown event type: {envelope.type}", cid))
            return
        try:
            payload = model.model_validate(envelope.payload)
        except ValidationError as exc:
            reply(self.conn, error_event("validation_error", "Invalid payload", cid, _errors(exc)))
            return

        try:
            await self._dispatch(envelope.type, payload, cid)
        except AppError as exc:
            reply(self.conn, error_event(exc.code, exc.message, cid, exc.details))
        except TranslationError as exc:
            reply(self.conn, error_event(exc.code, exc.message, cid))
        except Exception:  # noqa: BLE001 - never kill the socket for a handler bug / DB blip
            logger.exception("ws handler error", extra={"event": envelope.type})
            reply(self.conn, error_event("internal_error", "Could not process event, please retry", cid))

    async def _dispatch(self, event_type: str, payload: object, cid: str | None) -> None:
        match payload:
            case MessageSendPayload():
                if not self.send_limiter.allow(str(self.user.id)):
                    reply(self.conn, error_event("rate_limited", "Sending too fast, slow down", cid))
                    return
                # Reload so a language change made over REST applies immediately.
                sender = await self.load_user(self.user.id) or self.user
                await self.messages.send(sender, payload.conversation_id, payload.text,
                                         payload.client_message_id, payload.source_language, cid)
            case MessageReadPayload():
                await self.messages.mark_read(self.user, payload.conversation_id, payload.message_id, cid)
            case TypingPayload():
                await self.messages.typing(self.user, payload.conversation_id, event_type == ClientEvent.TYPING_START)
            case _:
                reply(self.conn, server_event(ServerEvent.PONG, {}, cid))

"""Messaging workflow shared by the WebSocket handler and REST endpoints.

send():
  1. validate membership + text (the sender comes from authentication, never from the client)
  2. persist the original message, per-recipient receipts and `pending` translation rows in one
     transaction; idempotent on (sender_id, client_message_id)
  3. deliver `message.created` immediately (the sender's copy carries the correlation_id as ack);
     online recipients are marked delivered
  4. hand translation jobs to MessageTranslationService, which pushes `message.translated`
"""

import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.exceptions import AppError, NotFoundError
from app.core.metrics import metrics
from app.features.conversations import repository as conv_repo
from app.features.conversations.service import require_membership
from app.features.messages import repository as msg_repo
from app.features.messages.models import Message, MessageReceipt
from app.features.messages.schemas import MessageOut
from app.features.messages.serializers import message_out
from app.features.messages.translation_jobs import MessageTranslationService
from app.features.translation.language_detection import detect_language, dominant_script
from app.features.users.models import User
from app.shared.schemas import CursorPage, to_payload, uuid_strings
from app.websocket.manager import ConnectionManager
from app.websocket.protocol import ServerEvent, server_event

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class MessageService:
    def __init__(self, settings: Settings, sessions: async_sessionmaker[AsyncSession],
                 manager: ConnectionManager, translations: MessageTranslationService) -> None:
        self.settings = settings
        self.sessions = sessions
        self.manager = manager
        self.translations = translations

    # ------------------------------------------------------------------ send
    async def send(self, sender: User, conversation_id: uuid.UUID, text: str, client_message_id: str,
                   source_language: str | None, correlation_id: str | None = None) -> tuple[MessageOut, bool]:
        """Persist and deliver a message. Returns (message, created); created=False for a retried send."""
        started = time.perf_counter()
        text = self._validate_text(text)
        # Explicit choice wins; otherwise detect from the script (English typed by a Hindi reader
        # must not be labelled Hindi).
        src = source_language or detect_language(text, sender.preferred_language, self.settings.enabled_languages)

        async with self.sessions() as session:
            conversation = await require_membership(session, conversation_id, sender.id)

            existing = await msg_repo.get_by_client_id(session, sender.id, client_message_id)
            if existing is not None:
                return self._ack_duplicate(existing, sender.id, conversation_id, correlation_id), False

            recipients = [m.user for m in conversation.members if m.user_id != sender.id and m.user.is_active]
            if not recipients:
                raise AppError("This person has deleted their account", code="recipient_deleted", status_code=409)

            message = Message(conversation_id=conversation_id, sender_id=sender.id,
                              client_message_id=client_message_id, original_text=text, source_language=src)
            msg_repo.add(session, message)
            try:
                await session.flush()
            except IntegrityError:
                # A concurrent retry with the same client_message_id won the race.
                await session.rollback()
                existing = await msg_repo.get_by_client_id(session, sender.id, client_message_id)
                if existing is None:
                    raise
                return message_out(existing), False

            now = _now()
            for user in recipients:
                msg_repo.add(session, MessageReceipt(
                    message_id=message.id, user_id=user.id,
                    delivered_at=now if self.manager.is_online(user.id) else None))
            # Emoji/numbers/punctuation only: nothing to translate, everyone reads it as-is.
            targets = set() if dominant_script(text) is None else {u.preferred_language for u in recipients} - {src}
            jobs = self.translations.add_pending(session, message.id, src, targets)
            conversation.last_message_at = now
            await session.commit()
            await session.refresh(message, ["translations", "receipts"])
            out = message_out(message)
            member_ids = [m.user_id for m in conversation.members]

        metrics.incr("messages_sent")
        payload = {"message": to_payload(out), "duplicate": False}
        self.manager.send_to_user(sender.id, server_event(ServerEvent.MESSAGE_CREATED, payload, correlation_id))
        self.manager.send_to_users([u for u in member_ids if u != sender.id],
                                   server_event(ServerEvent.MESSAGE_CREATED, payload))
        self.translations.schedule(out.id, conversation_id, text, src, jobs)
        metrics.observe("message_processing_seconds", time.perf_counter() - started)
        return out, True

    def _validate_text(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise AppError("Message text is empty", code="empty_message")
        if len(text) > self.settings.MAX_MESSAGE_LENGTH:
            raise AppError(f"Message exceeds {self.settings.MAX_MESSAGE_LENGTH} characters", code="message_too_long")
        return text

    def _ack_duplicate(self, existing: Message, sender_id: uuid.UUID, conversation_id: uuid.UUID,
                       correlation_id: str | None) -> MessageOut:
        if existing.conversation_id != conversation_id:
            raise AppError("client_message_id already used in another conversation",
                           code="duplicate_client_message_id", status_code=409)
        metrics.incr("messages_duplicate")
        out = message_out(existing)
        self.manager.send_to_user(sender_id, server_event(
            ServerEvent.MESSAGE_CREATED, {"message": to_payload(out), "duplicate": True}, correlation_id))
        return out

    # ------------------------------------------------------------------ history
    async def history(self, user_id: uuid.UUID, conversation_id: uuid.UUID, limit: int,
                      before: uuid.UUID | None) -> CursorPage[MessageOut]:
        """Oldest-first page of messages older than `before`. Fetching counts as delivery."""
        async with self.sessions() as session:
            if not await conv_repo.is_member(session, conversation_id, user_id):
                raise NotFoundError("Conversation not found", code="conversation_not_found")
            cursor = None
            if before is not None:
                cursor = await msg_repo.get(session, before)
                if cursor is None or cursor.conversation_id != conversation_id:
                    raise AppError("Invalid cursor", code="invalid_cursor")
            rows, has_more = await msg_repo.history(session, conversation_id, limit, cursor)
            items = [message_out(m) for m in rows]
        incoming = [m.id for m in rows if m.sender_id != user_id]
        if incoming:
            await self.mark_delivered(user_id, conversation_id, incoming)
        return CursorPage(items=items, next_cursor=str(rows[0].id) if has_more and rows else None,
                          has_more=has_more)

    # ------------------------------------------------------------------ receipts
    async def mark_delivered(self, user_id: uuid.UUID, conversation_id: uuid.UUID,
                             message_ids: list[uuid.UUID]) -> None:
        async with self.sessions() as session:
            now = _now()
            delivered = await msg_repo.mark_delivered(session, user_id, message_ids, now)
            senders = await msg_repo.senders_of(session, delivered)
            await session.commit()
        by_sender: dict[uuid.UUID, list[uuid.UUID]] = {}
        for message_id in delivered:
            by_sender.setdefault(senders[message_id], []).append(message_id)
        for sender_id, ids in by_sender.items():
            self.manager.send_to_user(sender_id, server_event(ServerEvent.MESSAGE_DELIVERED, {
                "conversation_id": str(conversation_id), "message_ids": uuid_strings(ids),
                "user_id": str(user_id), "delivered_at": now.isoformat(),
            }))

    async def mark_read(self, user: User, conversation_id: uuid.UUID, message_id: uuid.UUID,
                        correlation_id: str | None = None) -> list[uuid.UUID]:
        """Mark `message_id` and everything before it as read by `user`; notify all members."""
        async with self.sessions() as session:
            conversation = await require_membership(session, conversation_id, user.id)
            message = await msg_repo.get(session, message_id)
            if message is None or message.conversation_id != conversation_id:
                raise NotFoundError("Message not found", code="message_not_found")
            now = _now()
            read_ids = await msg_repo.mark_read_up_to(session, user.id, message, now)
            await conv_repo.set_last_read(session, conversation_id, user.id, message_id)
            await session.commit()
            member_ids = [m.user_id for m in conversation.members]
        self.manager.send_to_users(member_ids, server_event(ServerEvent.MESSAGE_READ, {
            "conversation_id": str(conversation_id), "user_id": str(user.id),
            "message_ids": uuid_strings(read_ids), "up_to_message_id": str(message_id), "read_at": now.isoformat(),
        }, correlation_id))
        return read_ids

    # ------------------------------------------------------------------ typing
    async def typing(self, user: User, conversation_id: uuid.UUID, started: bool) -> None:
        async with self.sessions() as session:
            conversation = await require_membership(session, conversation_id, user.id)
            others = [m.user_id for m in conversation.members if m.user_id != user.id]
        event = ServerEvent.TYPING_STARTED if started else ServerEvent.TYPING_STOPPED
        self.manager.send_to_users(others, server_event(event, {
            "conversation_id": str(conversation_id), "user_id": str(user.id),
        }))

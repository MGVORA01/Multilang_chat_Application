"""Per-message translation jobs: create pending rows, run them in the background, retry.

A translation job never modifies the original message; failures are stored on the translation row
and pushed to clients as `message.translated` with status "failed".
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import AppError, NotFoundError
from app.core.metrics import metrics
from app.features.conversations import repository as conv_repo
from app.features.messages import repository as msg_repo
from app.features.messages.models import MessageTranslation, TranslationStatus
from app.features.messages.schemas import TranslationOut
from app.features.messages.serializers import translation_out
from app.features.translation.service import TranslationService, public_error_message
from app.features.users.models import User
from app.integrations.translation.base import TranslationError, UnsupportedLanguagePairError
from app.shared.schemas import to_payload
from app.shared.tasks import BackgroundTasks
from app.websocket.manager import ConnectionManager
from app.websocket.protocol import ServerEvent, server_event

logger = logging.getLogger(__name__)


class MessageTranslationService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], manager: ConnectionManager,
                 translator: TranslationService, tasks: BackgroundTasks) -> None:
        self.sessions = sessions
        self.manager = manager
        self.translator = translator
        self.tasks = tasks

    async def recover(self) -> None:
        """At startup, jobs from a previous process can never finish: mark them failed (retryable)."""
        async with self.sessions() as session:
            count = await msg_repo.fail_stale_pending_translations(session)
            await session.commit()
        if count:
            logger.warning("marked stale pending translations as failed", extra={"count": count})

    def add_pending(self, session: AsyncSession, message_id: uuid.UUID, src: str, targets: set[str]) -> list[str]:
        """Add a `pending` row per target language (in the caller's transaction); return targets to run.

        Unsupported pairs get a `failed` row right away instead of a job.
        """
        jobs: list[str] = []
        for tgt in sorted(targets):
            try:
                model_name = self.translator.model_name(src, tgt)
            except UnsupportedLanguagePairError as exc:
                msg_repo.add(session, MessageTranslation(message_id=message_id, target_language=tgt,
                                                         status=TranslationStatus.FAILED,
                                                         error_message=public_error_message(exc)))
                continue
            msg_repo.add(session, MessageTranslation(message_id=message_id, target_language=tgt,
                                                     model_name=model_name, status=TranslationStatus.PENDING))
            jobs.append(tgt)
        return jobs

    def schedule(self, message_id: uuid.UUID, conversation_id: uuid.UUID, text: str, src: str,
                 targets: list[str]) -> None:
        for tgt in targets:
            self.tasks.spawn(self._run(message_id, conversation_id, text, src, tgt))

    async def retry(self, user: User, message_id: uuid.UUID, target_language: str | None) -> TranslationOut:
        """Retry a failed translation, or create one for a language that has none (e.g. after a
        language change). Completed/in-progress translations are returned unchanged."""
        async with self.sessions() as session:
            message = await msg_repo.get(session, message_id)
            if message is None or not await conv_repo.is_member(session, message.conversation_id, user.id):
                raise NotFoundError("Message not found", code="message_not_found")
            tgt = target_language or user.preferred_language
            try:
                model_name = self.translator.model_name(message.source_language, tgt)
            except UnsupportedLanguagePairError as exc:
                raise AppError(exc.message, code=exc.code) from exc
            translation = await msg_repo.get_translation_for(session, message_id, tgt)
            if translation is not None and translation.status in (TranslationStatus.COMPLETED,
                                                                  TranslationStatus.PENDING):
                return translation_out(translation)
            if translation is None:
                translation = MessageTranslation(message_id=message_id, target_language=tgt)
                msg_repo.add(session, translation)
            translation.status = TranslationStatus.PENDING
            translation.error_message = None
            translation.translated_text = None
            translation.model_name = model_name
            await session.commit()
            await session.refresh(translation)
            out = translation_out(translation)
            text, src, conversation_id = message.original_text, message.source_language, message.conversation_id
            members = await conv_repo.member_ids(session, conversation_id)

        metrics.incr("translation_retries")
        self.manager.send_to_users(members, server_event(
            ServerEvent.MESSAGE_TRANSLATED, to_payload(out) | {"conversation_id": str(conversation_id)}))
        self.schedule(message_id, conversation_id, text, src, [tgt])
        return out

    async def get_for_member(self, user_id: uuid.UUID, translation_id: uuid.UUID) -> TranslationOut:
        async with self.sessions() as session:
            translation = await msg_repo.get_translation(session, translation_id)
            if translation is not None:
                message = await msg_repo.get(session, translation.message_id)
                if message is not None and await conv_repo.is_member(session, message.conversation_id, user_id):
                    return translation_out(translation)
        raise NotFoundError("Translation not found", code="translation_not_found")

    async def _run(self, message_id: uuid.UUID, conversation_id: uuid.UUID, text: str, src: str, tgt: str) -> None:
        values = await self._translate(text, src, tgt)
        try:
            async with self.sessions() as session:
                translation = await msg_repo.get_translation_for(session, message_id, tgt)
                if translation is None:  # message deleted meanwhile
                    return
                for key, value in values.items():
                    setattr(translation, key, value)
                await session.commit()
                await session.refresh(translation)
                payload = to_payload(translation_out(translation))
                members = await conv_repo.member_ids(session, conversation_id)
        except Exception:  # noqa: BLE001 - DB down: the row stays pending/failed and can be retried
            logger.exception("failed to persist translation result", extra={"message_id": str(message_id)})
            metrics.incr("db_errors")
            return
        payload["conversation_id"] = str(conversation_id)
        self.manager.send_to_users(members, server_event(ServerEvent.MESSAGE_TRANSLATED, payload))

    async def _translate(self, text: str, src: str, tgt: str) -> dict[str, Any]:
        """Column values for the translation row: completed with text, or failed with a reason."""
        try:
            result = await self.translator.translate(text, src, tgt)
            return {"status": TranslationStatus.COMPLETED, "translated_text": result.text,
                    "model_name": result.model_name, "error_message": None, "translated_at": datetime.now(UTC)}
        except TranslationError as exc:
            logger.warning("translation job failed", extra={"src": src, "tgt": tgt, "code": exc.code,
                                                            "detail": exc.message[:300]})
            reason = public_error_message(exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("unexpected translation error")
            reason = f"Translation failed: {type(exc).__name__}"
        return {"status": TranslationStatus.FAILED, "translated_text": None, "error_message": reason,
                "translated_at": None}

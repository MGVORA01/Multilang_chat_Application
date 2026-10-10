"""Message history and translation-retry endpoints (sending happens over the WebSocket)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import MessageServiceDep, TranslationJobsDep
from app.features.auth.dependencies import CurrentUser
from app.features.messages.schemas import MessageOut, RetryTranslationRequest, TranslationOut
from app.features.translation.router import translate_rate_limit
from app.shared.schemas import CursorPage

router = APIRouter(tags=["messages"])


@router.get("/conversations/{conversation_id}/messages", response_model=CursorPage[MessageOut])
async def list_messages(
    conversation_id: uuid.UUID, user: CurrentUser, messages: MessageServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: Annotated[uuid.UUID | None, Query(description="Message ID cursor: return older messages")] = None,
) -> CursorPage[MessageOut]:
    return await messages.history(user.id, conversation_id, limit, before)


@router.post("/messages/{message_id}/translations/retry", response_model=TranslationOut,
             status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(translate_rate_limit)])
async def retry_translation(message_id: uuid.UUID, user: CurrentUser, jobs: TranslationJobsDep,
                            body: RetryTranslationRequest | None = None) -> TranslationOut:
    """Retry a failed translation, or request one for a language that has none yet.

    The result arrives as a `message.translated` WebSocket event; this returns the current row.
    """
    return await jobs.retry(user, message_id, body.target_language if body else None)

"""Ad-hoc translation endpoints (composer live preview, testing) and translation lookup."""

import uuid

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import TranslationJobsDep, TranslatorDep
from app.core.exceptions import AppError, RateLimitedError, ServiceUnavailableError
from app.features.auth.dependencies import CurrentUser
from app.features.messages.schemas import TranslationOut
from app.features.translation.schemas import TranslateRequest, TranslateResponse
from app.features.translation.service import public_error_message
from app.integrations.translation.base import (
    ModelUnavailableError,
    TranslationError,
    TranslationQueueFullError,
    TranslationTimeoutError,
    UnsupportedLanguagePairError,
)

router = APIRouter(tags=["translations"])


def translate_rate_limit(request: Request, user: CurrentUser) -> None:
    """Per-user budget for anything that triggers model inference on demand (previews, retries)."""
    if not request.app.state.translate_limiter.allow(str(user.id)):
        raise RateLimitedError("Too many translation requests")


@router.post("/translations", response_model=TranslateResponse, dependencies=[Depends(translate_rate_limit)])
async def translate(body: TranslateRequest, _: CurrentUser, translator: TranslatorDep) -> TranslateResponse:
    """Translate text directly. Results are cached, so sending previewed text is translated instantly."""
    try:
        result = await translator.translate(body.text, body.source_language, body.target_language, adhoc=True)
    except UnsupportedLanguagePairError as exc:
        raise AppError(exc.message, code=exc.code) from exc
    except (TranslationQueueFullError, ModelUnavailableError, TranslationTimeoutError) as exc:
        raise ServiceUnavailableError(public_error_message(exc), code=exc.code) from exc
    except TranslationError as exc:
        raise AppError(public_error_message(exc), code=exc.code, status_code=502) from exc
    return TranslateResponse(translated_text=result.text, source_language=body.source_language,
                             target_language=body.target_language, model_name=result.model_name,
                             duration_ms=result.duration_ms, cached=result.cached)


@router.get("/translations/{translation_id}", response_model=TranslationOut)
async def get_translation(translation_id: uuid.UUID, user: CurrentUser, jobs: TranslationJobsDep) -> TranslationOut:
    return await jobs.get_for_member(user.id, translation_id)

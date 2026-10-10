"""Languages, health and metrics endpoints."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.dependencies import ManagerDep, SessionDep, TranslatorDep
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.languages import enabled_languages
from app.core.metrics import metrics
from app.features.auth.dependencies import CurrentUser
from app.features.system.schemas import LanguageOut

router = APIRouter(tags=["system"])


@router.get("/languages", response_model=list[LanguageOut])
async def languages() -> list[LanguageOut]:
    return [LanguageOut(code=lang.code, name=lang.name, native_name=lang.native_name) for lang in enabled_languages()]


@router.get("/health")
async def health(session: SessionDep, translator: TranslatorDep) -> dict[str, object]:
    """Database reachability and per-model load state (models may still be loading)."""
    try:
        await session.execute(text("SELECT 1"))
        db = "ok"
    except Exception:  # noqa: BLE001
        db = "unavailable"
    models = translator.engine.status()
    translation_ok = translator.backend != "indictrans2" or all(m.get("state") != "error" for m in models.values())
    # Unauthenticated endpoint: in production expose states only, never error details.
    show_errors = get_settings().APP_ENV != "production"
    return {"status": "ok" if db == "ok" else "degraded", "database": db,
            "translation": {"backend": translator.backend, "ok": translation_ok,
                            "models": {k: {"state": v.get("state"), "error": v.get("error") if show_errors else None}
                                       for k, v in models.items()}}}


@router.get("/metrics")
async def get_metrics(_: CurrentUser, manager: ManagerDep, translator: TranslatorDep) -> dict[str, object]:
    """Operational counters. No role system exists, so this is off unless METRICS_ENABLED."""
    if not get_settings().METRICS_ENABLED:
        raise NotFoundError("Not found")
    return {"metrics": metrics.snapshot(), "ws_connections": manager.connection_count(),
            "translation": translator.status()}

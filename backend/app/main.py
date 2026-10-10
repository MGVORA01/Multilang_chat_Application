"""FastAPI application factory and lifespan wiring (singletons live on app.state)."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

import app.models  # noqa: F401 - registers every ORM model before first use
from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.languages import enabled_languages
from app.core.logging import configure_logging
from app.core.middleware import BodySizeLimitMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import SlidingWindowLimiter
from app.db.session import create_engine, create_session_factory
from app.features.messages.service import MessageService
from app.features.messages.translation_jobs import MessageTranslationService
from app.features.presence.service import PresenceService
from app.features.translation.service import TranslationService
from app.integrations.translation.factory import build_engine
from app.shared.tasks import BackgroundTasks
from app.websocket.manager import ConnectionManager
from app.websocket.router import router as ws_router
from app.websocket.tickets import TicketStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    enabled_languages()  # fail fast on a bad SUPPORTED_LANGUAGES value

    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    tasks = BackgroundTasks()
    manager = ConnectionManager(settings.WS_SEND_QUEUE_SIZE)
    translator = TranslationService(settings, build_engine(settings))
    translation_jobs = MessageTranslationService(sessions, manager, translator, tasks)

    state = app.state
    state.engine = engine
    state.session_factory = sessions
    state.tasks = tasks
    state.manager = manager
    state.tickets = TicketStore(settings.WS_TICKET_EXPIRE_SECONDS)
    state.auth_limiter = SlidingWindowLimiter(settings.AUTH_RATE_LIMIT_PER_MINUTE, 60)
    state.login_limiter = SlidingWindowLimiter(settings.LOGIN_ATTEMPTS_PER_ACCOUNT_15MIN, 15 * 60)
    state.ticket_limiter = SlidingWindowLimiter(settings.WS_TICKETS_PER_MINUTE, 60)
    state.ws_send_limiter = SlidingWindowLimiter(settings.WS_MESSAGES_PER_10S, 10)
    state.translate_limiter = SlidingWindowLimiter(settings.TRANSLATE_RATE_LIMIT_PER_MINUTE, 60)
    state.translator = translator
    state.translation_jobs = translation_jobs
    state.messages = MessageService(settings, sessions, manager, translation_jobs)
    state.presence = PresenceService(sessions, manager, tasks)

    await translation_jobs.recover()
    logger.info("loading translation models", extra={"backend": settings.TRANSLATION_BACKEND,
                                                     "preload": settings.TRANSLATION_PRELOAD})
    await translator.startup()
    logger.info("startup complete", extra={"translation": translator.status()["models"]})
    try:
        yield
    finally:
        await tasks.shutdown()
        await translator.shutdown()
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    app = FastAPI(title="Multilingual Chat", version="1.0.0", lifespan=lifespan,
                  docs_url="/api/docs" if settings.APP_ENV != "production" else None,
                  openapi_url="/api/openapi.json" if settings.APP_ENV != "production" else None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    # Outermost first: Host check, then body limit, then headers on every response (incl. errors).
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.APP_ENV == "production")
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)
    if "*" not in settings.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()

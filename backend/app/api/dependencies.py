"""Request-scoped dependencies: DB session, app-wide singletons and rate limits."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, RateLimitedError
from app.db.session import get_session
from app.features.messages.service import MessageService
from app.features.messages.translation_jobs import MessageTranslationService
from app.features.translation.service import TranslationService
from app.websocket.manager import ConnectionManager
from app.websocket.tickets import TicketStore

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_manager(request: Request) -> ConnectionManager:
    return request.app.state.manager


def get_translator(request: Request) -> TranslationService:
    return request.app.state.translator


def get_message_service(request: Request) -> MessageService:
    return request.app.state.messages


def get_translation_jobs(request: Request) -> MessageTranslationService:
    return request.app.state.translation_jobs


def get_tickets(request: Request) -> TicketStore:
    return request.app.state.tickets


ManagerDep = Annotated[ConnectionManager, Depends(get_manager)]
TranslatorDep = Annotated[TranslationService, Depends(get_translator)]
MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]
TranslationJobsDep = Annotated[MessageTranslationService, Depends(get_translation_jobs)]
TicketsDep = Annotated[TicketStore, Depends(get_tickets)]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def require_trusted_origin(request: Request) -> None:
    """CSRF defence in depth for cookie-authenticated endpoints (the cookie is already SameSite=Strict).

    Browsers always send Origin on cross-site POSTs; non-browser clients may omit it.
    """
    origin = (request.headers.get("origin") or "").rstrip("/")
    if origin and origin not in get_settings().allowed_origins:
        raise ForbiddenError("Origin not allowed", code="origin_not_allowed")


def auth_rate_limit(request: Request) -> None:
    """Per-IP limit for login/register/refresh/delete (brute-force protection)."""
    if not request.app.state.auth_limiter.allow(f"{request.url.path}:{client_ip(request)}"):
        raise RateLimitedError("Too many attempts, please wait a minute and try again")

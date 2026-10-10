"""Authenticated WebSocket endpoint: /ws/chat?ticket=<single-use ticket>.

Lifecycle: Origin check -> ticket redemption -> register connection -> `session.ready` ->
receive loop (idle timeout) -> unregister + presence. Frame handling lives in handlers.py.
"""

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.features.messages.service import MessageService
from app.features.presence.service import PresenceService
from app.features.users import repository as user_repo
from app.features.users.models import User
from app.websocket.handlers import FrameHandler
from app.websocket.manager import ConnectionManager
from app.websocket.protocol import CloseCode, ServerEvent, error_event, server_event

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/chat")
async def chat_socket(ws: WebSocket) -> None:
    settings = get_settings()
    manager: ConnectionManager = ws.app.state.manager
    presence: PresenceService = ws.app.state.presence
    messages: MessageService = ws.app.state.messages

    async def load_user(user_id: uuid.UUID) -> User | None:
        async with ws.app.state.session_factory() as session:
            return await user_repo.get_active_by_id(session, user_id)

    origin = (ws.headers.get("origin") or "").rstrip("/")
    # Browsers always send Origin (CORS does not protect WebSockets); non-browser clients may omit it.
    if origin and origin not in settings.allowed_origins:
        await ws.close(code=CloseCode.ORIGIN_NOT_ALLOWED, reason="origin not allowed")
        return

    user_id = ws.app.state.tickets.redeem(ws.query_params.get("ticket"))
    user = await load_user(user_id) if user_id else None
    await ws.accept()
    if user is None:
        await ws.send_json(error_event("unauthorized", "Invalid or expired WebSocket ticket"))
        await ws.close(code=CloseCode.UNAUTHORIZED, reason="unauthorized")
        return

    if manager.connections_of(user.id) >= settings.WS_MAX_CONNECTIONS_PER_USER:
        await ws.send_json(error_event("too_many_connections", "Too many open connections for this account"))
        await ws.close(code=CloseCode.TOO_MANY_CONNECTIONS, reason="too many connections")
        return

    conn, became_online = await manager.register(user.id, ws)
    logger.info("ws connected", extra={"user_id": str(user.id), "conn": conn.id})
    conn.enqueue(json.dumps(server_event(ServerEvent.SESSION_READY, {
        "user_id": str(user.id),
        "online_user_ids": [str(u) for u in await presence.online_contacts(user.id)],
        "heartbeat_seconds": settings.WS_IDLE_TIMEOUT_SECONDS,
    })))
    if became_online:
        await presence.went_online(user.id)

    handler = FrameHandler(conn, user, messages, load_user, settings.WS_MAX_MESSAGE_BYTES,
                           ws.app.state.ws_send_limiter, settings.WS_EVENTS_PER_10S)
    try:
        while not conn.closed:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=settings.WS_IDLE_TIMEOUT_SECONDS)
            except TimeoutError:
                await ws.close(code=CloseCode.IDLE_TIMEOUT, reason="idle timeout")
                break
            await handler.handle(raw)
    except (WebSocketDisconnect, RuntimeError):  # RuntimeError: already closed by the slow-client path
        pass
    finally:
        went_offline = await manager.unregister(conn)
        logger.info("ws disconnected", extra={"user_id": str(user.id), "conn": conn.id})
        if went_offline:
            presence.went_offline(user.id)

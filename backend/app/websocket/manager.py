"""In-memory WebSocket connection manager (single backend process).

- Multiple connections per user (e.g. phone + desktop).
- Each connection has a bounded outbound queue drained by its own writer task, so one slow
  client never blocks delivery to anyone else. A client whose queue overflows is disconnected.
- Events are only ever addressed to explicit user IDs; callers resolve recipients from
  conversation membership, so there is no broadcast-to-all path that could leak messages.

This does NOT work across multiple processes. For multi-worker deployments, publish events to
Redis Pub/Sub keyed by user ID and have each process deliver to its local connections
(see docs/architecture.md).
"""

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Iterable
from typing import Any

from fastapi import WebSocket

from app.core.metrics import metrics
from app.websocket.protocol import CloseCode

logger = logging.getLogger(__name__)


class ClientConnection:
    def __init__(self, user_id: uuid.UUID, websocket: WebSocket, queue_size: int) -> None:
        self.id = uuid.uuid4().hex
        self.user_id = user_id
        self.websocket = websocket
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=queue_size)
        self.writer: asyncio.Task[None] | None = None
        self.closed = False

    def enqueue(self, data: str) -> bool:
        if self.closed:
            return False
        try:
            self.queue.put_nowait(data)
            return True
        except asyncio.QueueFull:
            return False

    async def run_writer(self) -> None:
        try:
            while True:
                data = await self.queue.get()
                if data is None:
                    break
                await self.websocket.send_text(data)
        except Exception:  # noqa: BLE001 - socket gone; reader loop will clean up
            self.closed = True


class ConnectionManager:
    def __init__(self, queue_size: int = 256) -> None:
        self.queue_size = queue_size
        self._by_user: dict[uuid.UUID, dict[str, ClientConnection]] = {}

    async def register(self, user_id: uuid.UUID, websocket: WebSocket) -> tuple[ClientConnection, bool]:
        """Returns (connection, became_online)."""
        conn = ClientConnection(user_id, websocket, self.queue_size)
        conn.writer = asyncio.create_task(conn.run_writer(), name=f"ws-writer-{conn.id}")
        conns = self._by_user.setdefault(user_id, {})
        became_online = not conns
        conns[conn.id] = conn
        self._update_gauge()
        metrics.incr("ws_connects")
        return conn, became_online

    async def unregister(self, conn: ClientConnection) -> bool:
        """Returns True when this was the user's last connection (went offline)."""
        conn.closed = True
        conns = self._by_user.get(conn.user_id, {})
        conns.pop(conn.id, None)
        went_offline = not conns
        if went_offline:
            self._by_user.pop(conn.user_id, None)
        if conn.writer:
            with contextlib.suppress(asyncio.QueueFull):
                conn.queue.put_nowait(None)
            conn.writer.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await conn.writer
        self._update_gauge()
        metrics.incr("ws_disconnects")
        return went_offline

    def is_online(self, user_id: uuid.UUID) -> bool:
        return bool(self._by_user.get(user_id))

    def online_users(self) -> set[uuid.UUID]:
        return set(self._by_user)

    def connections_of(self, user_id: uuid.UUID) -> int:
        return len(self._by_user.get(user_id, {}))

    def connection_count(self) -> int:
        return sum(len(c) for c in self._by_user.values())

    def send_to_user(self, user_id: uuid.UUID, event: dict[str, Any]) -> int:
        """Queue `event` for every connection of `user_id`. Returns number of connections reached."""
        data = json.dumps(event, default=str, ensure_ascii=False)
        sent = 0
        for conn in list(self._by_user.get(user_id, {}).values()):
            if conn.enqueue(data):
                sent += 1
            else:
                logger.warning("ws send queue full, closing slow client", extra={"user_id": str(user_id)})
                metrics.incr("ws_slow_client_disconnects")
                conn.closed = True
                asyncio.create_task(self._close_quietly(conn))
        return sent

    def send_to_users(self, user_ids: Iterable[uuid.UUID], event: dict[str, Any]) -> None:
        for uid in set(user_ids):
            self.send_to_user(uid, event)

    async def disconnect_user(self, user_id: uuid.UUID, code: int, reason: str) -> None:
        """Close every connection of a user (e.g. account deleted)."""
        for conn in list(self._by_user.get(user_id, {}).values()):
            conn.closed = True
            await self._close_quietly(conn, code, reason)

    @staticmethod
    async def _close_quietly(conn: ClientConnection, code: int = CloseCode.SLOW_CLIENT, reason: str = "") -> None:
        with contextlib.suppress(Exception):
            await conn.websocket.close(code=code, reason=reason)

    def _update_gauge(self) -> None:
        metrics.gauge("ws_connections", self.connection_count())
        metrics.gauge("ws_online_users", len(self._by_user))

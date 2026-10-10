"""Connection manager, WebSocket tickets, rate limiter and background tasks (no database)."""

import asyncio
import json
import time
import uuid
from typing import Any

from app.core.rate_limit import SlidingWindowLimiter
from app.shared.tasks import BackgroundTasks
from app.websocket.manager import ConnectionManager
from app.websocket.protocol import CloseCode, ServerEvent, server_event
from app.websocket.tickets import TicketStore


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.closed_with: int | None = None

    async def send_text(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed_with = code


def test_manager_routes_only_to_addressed_users_and_tracks_presence() -> None:
    async def go() -> None:
        manager = ConnectionManager()
        alice, bob = uuid.uuid4(), uuid.uuid4()
        phone, desktop, bob_ws = FakeSocket(), FakeSocket(), FakeSocket()
        c1, first = await manager.register(alice, phone)  # type: ignore[arg-type]
        c2, second = await manager.register(alice, desktop)  # type: ignore[arg-type]
        c3, _ = await manager.register(bob, bob_ws)  # type: ignore[arg-type]
        assert first is True and second is False  # only the first connection flips presence
        assert manager.is_online(alice) and manager.connection_count() == 3

        assert manager.send_to_user(alice, server_event(ServerEvent.PONG, {})) == 2
        await asyncio.sleep(0.01)  # writer tasks drain the queues
        assert len(phone.sent) == len(desktop.sent) == 1 and bob_ws.sent == []

        assert await manager.unregister(c1) is False
        assert await manager.unregister(c2) is True  # last connection -> offline
        assert not manager.is_online(alice)
        await manager.disconnect_user(bob, CloseCode.ACCOUNT_DELETED, "account deleted")
        assert bob_ws.closed_with == CloseCode.ACCOUNT_DELETED
        await manager.unregister(c3)

    asyncio.run(go())


def test_ticket_is_single_use_and_expires() -> None:
    store = TicketStore(ttl_seconds=30)
    user_id = uuid.uuid4()
    ticket = store.issue(user_id)
    assert store.redeem(ticket) == user_id
    assert store.redeem(ticket) is None
    assert store.redeem(None) is None

    expired = TicketStore(ttl_seconds=0)
    t = expired.issue(user_id)
    time.sleep(0.01)
    assert expired.redeem(t) is None


def test_sliding_window_limiter() -> None:
    limiter = SlidingWindowLimiter(limit=2, window_seconds=60)
    assert [limiter.allow("k") for _ in range(3)] == [True, True, False]
    assert limiter.allow("other") is True  # keys are independent


def test_background_tasks_drain_then_cancel_on_shutdown() -> None:
    async def go() -> None:
        tasks = BackgroundTasks()
        finished: list[str] = []

        async def quick() -> None:
            await asyncio.sleep(0.01)
            finished.append("quick")

        async def stuck() -> None:
            await asyncio.sleep(60)

        tasks.spawn(quick())
        slow = tasks.spawn(stuck())
        await tasks.shutdown(grace_seconds=0.1)
        assert finished == ["quick"]  # in-flight work is allowed to finish
        assert slow.cancelled()  # anything still running after the grace period is cancelled
        assert len(tasks) == 0

    asyncio.run(go())

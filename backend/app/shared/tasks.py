"""Tracked fire-and-forget tasks with graceful shutdown."""

import asyncio
from collections.abc import Coroutine
from typing import Any


class BackgroundTasks:
    """Keeps references to detached tasks (so they aren't garbage-collected) and drains them on shutdown."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def __len__(self) -> int:
        return len(self._tasks)

    async def shutdown(self, grace_seconds: float = 5.0) -> None:
        """Let in-flight work finish (releasing DB sessions cleanly), then cancel what remains."""
        tasks = list(self._tasks)
        if not tasks:
            return
        _, pending = await asyncio.wait(tasks, timeout=grace_seconds)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

"""In-memory sliding-window rate limiter (single-process).

For multi-worker deployments move this to Redis.
"""

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._calls = 0

    _PURGE_EVERY = 1000

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        self._calls += 1
        if self._calls % self._PURGE_EVERY == 0:
            self._purge(now)
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def _purge(self, now: float) -> None:
        """Drop keys with no recent hits so many distinct keys (IPs, logins) can't grow memory forever."""
        for key in [k for k, h in self._hits.items() if not h or now - h[-1] > self.window]:
            del self._hits[key]

    def __len__(self) -> int:
        return len(self._hits)

    def reset(self) -> None:
        self._hits.clear()

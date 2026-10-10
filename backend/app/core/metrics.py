"""Tiny in-process metrics registry (counters, gauges, timing summaries).

Single-process only; replace with Prometheus if the deployment grows.
"""

import threading
from collections import defaultdict
from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, dict[str, float]] = {}

    def incr(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def observe(self, name: str, seconds: float) -> None:
        with self._lock:
            t = self._timings.setdefault(name, {"count": 0, "total": 0.0, "max": 0.0, "last": 0.0})
            t["count"] += 1
            t["total"] += seconds
            t["max"] = max(t["max"], seconds)
            t["last"] = seconds

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            timings = {
                k: {**v, "avg": (v["total"] / v["count"]) if v["count"] else 0.0}
                for k, v in self._timings.items()
            }
            return {"counters": dict(self._counters), "gauges": dict(self._gauges), "timings": timings}


metrics = Metrics()

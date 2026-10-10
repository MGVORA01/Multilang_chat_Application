"""Short-lived, single-use WebSocket tickets.

The browser WebSocket API cannot set an Authorization header, and long-lived JWTs must not go
in URLs (they end up in logs). Clients therefore call POST /api/v1/auth/ws-ticket with their
access token and connect with /ws/chat?ticket=<ticket>. A ticket expires after
WS_TICKET_EXPIRE_SECONDS and can be redeemed exactly once.

In-memory: valid for a single backend process. Move to Redis for multi-worker deployments.
"""

import secrets
import time
import uuid


class TicketStore:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        self._tickets: dict[str, tuple[uuid.UUID, float]] = {}

    def issue(self, user_id: uuid.UUID) -> str:
        self._purge()
        ticket = secrets.token_urlsafe(32)
        self._tickets[ticket] = (user_id, time.monotonic() + self.ttl)
        return ticket

    def redeem(self, ticket: str | None) -> uuid.UUID | None:
        if not ticket:
            return None
        entry = self._tickets.pop(ticket, None)
        if entry is None or entry[1] < time.monotonic():
            return None
        return entry[0]

    def _purge(self) -> None:
        now = time.monotonic()
        for key in [k for k, (_, exp) in self._tickets.items() if exp < now]:
            self._tickets.pop(key, None)

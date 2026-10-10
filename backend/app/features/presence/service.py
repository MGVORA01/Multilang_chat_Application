"""Online/offline presence, shared only with users who have a conversation in common."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.features.conversations import repository as conv_repo
from app.features.users import repository as user_repo
from app.shared.tasks import BackgroundTasks
from app.websocket.manager import ConnectionManager
from app.websocket.protocol import ServerEvent, server_event

logger = logging.getLogger(__name__)


class PresenceService:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], manager: ConnectionManager,
                 tasks: BackgroundTasks) -> None:
        self.sessions = sessions
        self.manager = manager
        self.tasks = tasks

    async def online_contacts(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        """Contacts of `user_id` who are connected right now."""
        async with self.sessions() as session:
            contacts = await conv_repo.contact_ids(session, user_id)
        return [u for u in contacts if self.manager.is_online(u)]

    async def went_online(self, user_id: uuid.UUID) -> None:
        await self._safe_broadcast(user_id, online=True)

    def went_offline(self, user_id: uuid.UUID) -> None:
        """Detached: must complete even if the disconnecting socket's task is being cancelled."""
        self.tasks.spawn(self._safe_broadcast(user_id, online=False))

    async def _safe_broadcast(self, user_id: uuid.UUID, online: bool) -> None:
        try:
            async with self.sessions() as session:
                last_seen = datetime.now(UTC)
                if not online:
                    await user_repo.touch_last_seen(session, user_id, last_seen)
                    await session.commit()
                contacts = await conv_repo.contact_ids(session, user_id)
        except Exception:  # noqa: BLE001 - presence is best-effort; never break the socket for it
            logger.exception("presence update failed", extra={"user_id": str(user_id)})
            return
        self.manager.send_to_users(contacts, server_event(ServerEvent.PRESENCE_UPDATED, {
            "user_id": str(user_id), "online": online, "last_seen_at": last_seen.isoformat(),
        }))

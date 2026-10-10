"""ORM -> API conversions for users."""

from app.features.users.models import User
from app.features.users.schemas import UserPublic
from app.websocket.manager import ConnectionManager


def user_public(user: User, manager: ConnectionManager | None = None, *, reveal_presence: bool = True) -> UserPublic:
    """Public profile. Presence (online / last seen) is private: only shown to people who share a
    conversation with the user (`reveal_presence`), mirroring the WebSocket presence rules."""
    out = UserPublic.model_validate(user)
    out.is_deleted = not user.is_active
    if reveal_presence:
        out.is_online = bool(manager and manager.is_online(user.id)) and user.is_active
    else:
        out.is_online = False
        out.last_seen_at = None
    return out

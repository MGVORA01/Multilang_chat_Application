"""Persistence for refresh tokens."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import RefreshToken


def add_refresh_token(session: AsyncSession, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> None:
    session.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))


async def get_refresh_token_for_update(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    """Row-locked lookup so two concurrent refreshes can't both rotate the same token."""
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID, when: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=when)
    )

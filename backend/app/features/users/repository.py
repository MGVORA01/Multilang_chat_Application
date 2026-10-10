"""Persistence for users."""

import uuid
from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User


async def get_active_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    user = await session.get(User, user_id)
    return user if user and user.is_active else None


async def get_by_login(session: AsyncSession, login: str) -> User | None:
    login = login.strip().lower()
    stmt = select(User).where(or_(User.username == login, User.email == login))
    return (await session.execute(stmt)).scalar_one_or_none()


async def exists_username_or_email(session: AsyncSession, username: str, email: str) -> tuple[bool, bool]:
    rows = (await session.execute(
        select(User.username, User.email).where(or_(User.username == username, User.email == email))
    )).all()
    return any(r.username == username for r in rows), any(r.email == email for r in rows)


async def search(session: AsyncSession, query: str | None, exclude_id: uuid.UUID,
                 limit: int, offset: int) -> tuple[list[User], int]:
    conditions = [User.is_active.is_(True), User.id != exclude_id]
    if query:
        pattern = "%" + query.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(or_(User.username.like(pattern, escape="\\"),
                              func.lower(User.display_name).like(pattern, escape="\\")))
    total = (await session.execute(select(func.count()).select_from(User).where(*conditions))).scalar_one()
    rows = (await session.execute(
        select(User).where(*conditions).order_by(User.display_name, User.id).limit(limit).offset(offset)
    )).scalars().all()
    return list(rows), total


def add(session: AsyncSession, user: User) -> None:
    session.add(user)


async def delete(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Hard-delete; ON DELETE CASCADE removes tokens, memberships, messages and receipts."""
    await session.execute(sa_delete(User).where(User.id == user_id))


async def touch_last_seen(session: AsyncSession, user_id: uuid.UUID, when: datetime) -> None:
    await session.execute(update(User).where(User.id == user_id).values(last_seen_at=when))

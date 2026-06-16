"""VA + assignment resolution."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Track
from app.models.va import Va
from app.models.va_assignment import VaAssignment


async def resolve_assignee(
    session: AsyncSession, *, user_id: UUID, track: Track | None
) -> Va | None:
    """The VA assigned to this hunter (and track, or all-tracks). Track-specific
    assignment wins over an all-tracks one."""
    stmt = select(VaAssignment).where(VaAssignment.user_id == user_id)
    assignments = list((await session.execute(stmt)).scalars().all())
    if not assignments:
        return None
    exact = [a for a in assignments if a.track == track]
    catchall = [a for a in assignments if a.track is None]
    chosen = (exact or catchall or assignments)[0]
    return await session.get(Va, chosen.va_id)

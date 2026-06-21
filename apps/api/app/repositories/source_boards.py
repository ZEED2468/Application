"""Board-token data access for the board-scraper sources."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import JobSourceName
from app.models.source_board import SourceBoard


async def active_by_source(session: AsyncSession) -> dict[JobSourceName, list[str]]:
    """{source: [active tokens]} — fed to each board scraper during discovery."""
    rows = (
        await session.execute(select(SourceBoard).where(SourceBoard.is_active.is_(True)))
    ).scalars().all()
    out: dict[JobSourceName, list[str]] = {}
    for r in rows:
        out.setdefault(r.source, []).append(r.token)
    return out


async def list_all(session: AsyncSession) -> list[SourceBoard]:
    return list(
        (await session.execute(
            select(SourceBoard).order_by(SourceBoard.source, SourceBoard.created_at.desc())
        )).scalars().all()
    )


async def create(
    session: AsyncSession, *, source: JobSourceName, token: str, label: str | None
) -> SourceBoard:
    board = SourceBoard(source=source, token=token.strip(), label=(label or None))
    session.add(board)
    await session.flush()
    return board


async def get(session: AsyncSession, board_id: UUID) -> SourceBoard | None:
    return await session.get(SourceBoard, board_id)

"""Admin: manage the per-company board tokens the board scrapers pull from."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db import get_session
from app.deps import require_admin
from app.models.user import User
from app.repositories import source_boards as boards_repo
from app.schemas.platforms import _BOARD_SOURCES, SourceBoardCreate, SourceBoardOut

router = APIRouter(prefix="/source-boards", tags=["admin"])


class BoardActive(BaseModel):
    is_active: bool


@router.get("", response_model=list[SourceBoardOut])
async def list_boards(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[SourceBoardOut]:
    return await boards_repo.list_all(session)


@router.post("", response_model=SourceBoardOut)
async def create_board(
    body: SourceBoardCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SourceBoardOut:
    if body.source not in _BOARD_SOURCES:
        raise ConflictError(
            "Only greenhouse, lever, and ashby use board tokens "
            "(adzuna/serpapi search by keyword)."
        )
    return await boards_repo.create(
        session, source=body.source, token=body.token, label=body.label
    )


@router.patch("/{board_id}", response_model=SourceBoardOut)
async def set_board_active(
    board_id: UUID, body: BoardActive,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> SourceBoardOut:
    board = await boards_repo.get(session, board_id)
    if board is None:
        raise NotFoundError("Board not found")
    board.is_active = body.is_active
    await session.flush()
    return board

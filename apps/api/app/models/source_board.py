"""source_board — a per-company board token for the board-scraper sources.

Greenhouse / Lever / Ashby fetch by company token (`query.boards`); this table is
where those tokens live so discovery can actually pull from them. Admin-managed and
global (applies to every hunter's discovery); a per-hunter scope can come later.
"""

import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import JobSourceName
from app.db import Base
from app.models.base import TimestampMixin, pk


class SourceBoard(Base, TimestampMixin):
    __tablename__ = "source_board"

    id: Mapped[uuid.UUID] = pk()
    source: Mapped[JobSourceName] = mapped_column(
        Enum(JobSourceName, native_enum=False), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(200), nullable=False)  # company slug/board id
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

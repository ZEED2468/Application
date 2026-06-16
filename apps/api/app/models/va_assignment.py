"""va_assignment — links a VA to hunter(s)/track(s). Supports shared OR per-hunter.

`track = NULL` means the VA covers all tracks for that hunter.
"""

import uuid

from sqlalchemy import Enum, ForeignKey, Index, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Track
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class VaAssignment(Base, TimestampMixin):
    __tablename__ = "va_assignment"
    __table_args__ = (
        UniqueConstraint("va_id", "user_id", "track", name="uq_assignment"),
        Index("ix_assignment_user_track", "user_id", "track"),
    )

    id: Mapped[uuid.UUID] = pk()
    va_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("va.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = user_fk()
    track: Mapped[Track | None] = mapped_column(
        Enum(Track, native_enum=False), nullable=True
    )

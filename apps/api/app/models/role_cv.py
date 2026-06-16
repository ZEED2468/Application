"""role_cv — a per (user, track) uploaded source CV.

A hunter selects multiple roles at onboarding and uploads one CV per role. The
manual-path matcher picks the right `role_cv` by JD role-title -> track.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ParseStatus, Track
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class RoleCv(Base, TimestampMixin):
    __tablename__ = "role_cv"
    __table_args__ = (UniqueConstraint("user_id", "track", name="uq_role_cv_user_track"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    track: Mapped[Track] = mapped_column(Enum(Track, native_enum=False), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # R2
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, native_enum=False), default=ParseStatus.pending, nullable=False
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

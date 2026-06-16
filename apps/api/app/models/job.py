"""job — a discovered posting, scoped + deduped per hunter."""

import uuid

from sqlalchemy import Enum, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import JobSourceName, JobStatus, Origin, Track
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class Job(Base, TimestampMixin):
    __tablename__ = "job"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_job_user_dedupe"),
        Index("ix_job_user_status", "user_id", "status"),
        Index("ix_job_user_track", "user_id", "track"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    source: Mapped[JobSourceName] = mapped_column(
        Enum(JobSourceName, native_enum=False), nullable=False
    )
    source_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # How the job entered the system. Both paths produce identical objects.
    origin: Mapped[Origin] = mapped_column(
        Enum(Origin, native_enum=False), default=Origin.auto, nullable=False
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    track: Mapped[Track | None] = mapped_column(Enum(Track, native_enum=False), nullable=True)
    track_override: Mapped[Track | None] = mapped_column(
        Enum(Track, native_enum=False), nullable=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.discovered, nullable=False
    )
    raw: Mapped[dict] = mapped_column(JsonB, default=dict)

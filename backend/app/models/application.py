"""application — a job a VA submits, with lifecycle status."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ApplicationStatus
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class Application(Base, TimestampMixin):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_application_job"),
        Index("ix_application_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_cv_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("generated_cv.id", ondelete="SET NULL"), nullable=True
    )
    va_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("va.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, native_enum=False),
        default=ApplicationStatus.draft,
        nullable=False,
    )
    submission_channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

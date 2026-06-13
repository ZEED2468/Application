"""generated_cv — tailored CV artifact per job (.tex + .pdf in R2)."""

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CvStatus
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class GeneratedCv(Base, TimestampMixin):
    __tablename__ = "generated_cv"
    __table_args__ = (UniqueConstraint("job_id", name="uq_cv_job"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    master_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("master_profile.id", ondelete="SET NULL"), nullable=True
    )
    cv_json: Mapped[dict] = mapped_column(JsonB, default=dict)
    latex_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    tex_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tailoring_diff: Mapped[dict] = mapped_column(JsonB, default=dict)
    status: Mapped[CvStatus] = mapped_column(
        Enum(CvStatus, native_enum=False), default=CvStatus.rendering, nullable=False
    )

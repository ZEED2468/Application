"""cover_letter + cover_letter_template — the 3-paragraph tailored letter and the
per-user onboarding base it is seeded from."""

import uuid

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import CoverLetterStatus
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class CoverLetterTemplate(Base, TimestampMixin):
    __tablename__ = "cover_letter_template"
    __table_args__ = (UniqueConstraint("user_id", name="uq_cl_template_user"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)


class CoverLetter(Base, TimestampMixin):
    __tablename__ = "cover_letter"
    __table_args__ = (UniqueConstraint("job_id", name="uq_cover_letter_job"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cover_letter_template.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)  # 3-paragraph text
    tex_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CoverLetterStatus] = mapped_column(
        Enum(CoverLetterStatus, native_enum=False),
        default=CoverLetterStatus.rendering,
        nullable=False,
    )

"""contact — an Apollo person at the target company, plus the enriched hook."""

import uuid

from sqlalchemy import Float, ForeignKey, Index, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class Contact(Base, TimestampMixin):
    __tablename__ = "contact"
    __table_args__ = (
        UniqueConstraint("job_id", "email", name="uq_contact_job_email"),
        Index("ix_contact_user_email", "user_id", "email"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role_type: Mapped[str | None] = mapped_column(String(64), nullable=True)  # engineer|hm|recruiter
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    linkedin: Mapped[str | None] = mapped_column(Text, nullable=True)
    apollo_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

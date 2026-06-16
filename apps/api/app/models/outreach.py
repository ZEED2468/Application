"""outreach — one sent (or drafted) message in a sequence step."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OutreachStatus, SequenceStep
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class Outreach(Base, TimestampMixin):
    __tablename__ = "outreach"
    __table_args__ = (
        UniqueConstraint(
            "application_id", "contact_id", "sequence_step", name="uq_outreach_step"
        ),
        Index("ix_outreach_status_next", "status", "next_action_at"),
        Index("ix_outreach_user_sent", "user_id", "sent_at"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contact.id", ondelete="CASCADE"), nullable=False
    )
    sending_domain_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sending_domain.id", ondelete="RESTRICT"), nullable=False
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("thread.id", ondelete="SET NULL"), nullable=True
    )

    sequence_step: Mapped[SequenceStep] = mapped_column(
        Enum(SequenceStep, native_enum=False), default=SequenceStep.first, nullable=False
    )
    status: Mapped[OutreachStatus] = mapped_column(
        Enum(OutreachStatus, native_enum=False), default=OutreachStatus.drafted, nullable=False
    )
    reply_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

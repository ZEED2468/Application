"""dossier — assembled context pushed to a VA on WhatsApp. Stamped with owner."""

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
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DossierStatus
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class Dossier(Base, TimestampMixin):
    __tablename__ = "dossier"
    __table_args__ = (
        Index("ix_dossier_va_status", "va_id", "status"),
        Index("ix_dossier_thread", "thread_id"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()  # owning hunter — stamped on every dossier
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("thread.id", ondelete="CASCADE"), nullable=False
    )
    reply_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reply.id", ondelete="CASCADE"), nullable=False
    )
    va_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("va.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JsonB, default=dict)
    status: Mapped[DossierStatus] = mapped_column(
        Enum(DossierStatus, native_enum=False), default=DossierStatus.pushed, nullable=False
    )
    bridge_message_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

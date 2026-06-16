"""thread — an email conversation per outreach. `reply_address` is the primary
inbound match key (apply+<jobId>@<domain>)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ThreadState
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class Thread(Base, TimestampMixin):
    __tablename__ = "thread"
    __table_args__ = (
        UniqueConstraint("reply_address", name="uq_thread_reply_address"),
        Index("ix_thread_root_message", "root_message_id"),
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
    reply_address: Mapped[str] = mapped_column(String(320), nullable=False)
    root_message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    state: Mapped[ThreadState] = mapped_column(
        Enum(ThreadState, native_enum=False), default=ThreadState.open, nullable=False
    )
    last_inbound_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_outbound_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

"""reply — an inbound or outbound message within a thread."""

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

from app.core.enums import ReplyClassification, ReplyDirection
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class Reply(Base, TimestampMixin):
    __tablename__ = "reply"
    __table_args__ = (
        Index("ix_reply_thread_received", "thread_id", "received_at"),
        Index("ix_reply_message_id", "message_id"),
        Index("ix_reply_in_reply_to", "in_reply_to"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("thread.id", ondelete="CASCADE"), nullable=False, index=True
    )
    direction: Mapped[ReplyDirection] = mapped_column(
        Enum(ReplyDirection, native_enum=False), nullable=False
    )
    from_addr: Mapped[str | None] = mapped_column(String(320), nullable=True)
    to_addr: Mapped[str | None] = mapped_column(String(320), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    in_reply_to: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification: Mapped[ReplyClassification | None] = mapped_column(
        Enum(ReplyClassification, native_enum=False), nullable=True
    )
    suggested_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw: Mapped[dict] = mapped_column(JsonB, default=dict)
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

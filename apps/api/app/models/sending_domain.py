"""sending_domain — one (user, track) -> one domain. 9 rows total."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DnsStatus, Track, WarmupStage
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class SendingDomain(Base, TimestampMixin):
    __tablename__ = "sending_domain"
    __table_args__ = (
        UniqueConstraint("user_id", "track", name="uq_domain_user_track"),
        UniqueConstraint("domain", name="uq_domain_name"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    track: Mapped[Track] = mapped_column(Enum(Track, native_enum=False), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    resend_domain_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    dkim_status: Mapped[DnsStatus] = mapped_column(
        Enum(DnsStatus, native_enum=False), default=DnsStatus.pending, nullable=False
    )
    spf_status: Mapped[DnsStatus] = mapped_column(
        Enum(DnsStatus, native_enum=False), default=DnsStatus.pending, nullable=False
    )
    dmarc_status: Mapped[DnsStatus] = mapped_column(
        Enum(DnsStatus, native_enum=False), default=DnsStatus.pending, nullable=False
    )
    dns_records: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob from provider

    warmup_stage: Mapped[WarmupStage] = mapped_column(
        Enum(WarmupStage, native_enum=False), default=WarmupStage.stage_1, nullable=False
    )
    warmup_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    daily_sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_count_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    pause_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    bounce_rate: Mapped[float] = mapped_column(default=0.0, nullable=False)
    complaint_rate: Mapped[float] = mapped_column(default=0.0, nullable=False)

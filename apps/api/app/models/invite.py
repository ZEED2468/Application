"""invite — a one-time, email-scoped key that gates account signup.

Admins invite hunters; hunters invite their VAs. The 6-char code is never stored
(only its SHA-256 hash, like `refresh_token`); it travels to the invitee via a
copyable `/signup?email=…&key=…` link. Single-use + expiring.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import InviteKind, InviteStatus, Track
from app.db import Base
from app.models.base import TimestampMixin, pk


class Invite(Base, TimestampMixin):
    __tablename__ = "invite"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)  # lowercased
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    kind: Mapped[InviteKind] = mapped_column(
        Enum(InviteKind, native_enum=False), nullable=False
    )
    # admin for hunter invites; the owning hunter for VA invites.
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # VA-only fields captured at invite time (the hunter knows them).
    va_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    va_whatsapp_jid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    track: Mapped[Track | None] = mapped_column(
        Enum(Track, native_enum=False), nullable=True
    )  # None = all-tracks assignment
    # Set on admin invites: the platform the new admin is attached to.
    platform_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("platform.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[InviteStatus] = mapped_column(
        Enum(InviteStatus, native_enum=False), default=InviteStatus.pending, nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

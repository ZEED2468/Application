"""user (hunter) — auth + identity. Also `refresh_token` for revocable sessions."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import UserRole
from app.db import Base
from app.models.base import TimestampMixin, pk


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False), default=UserRole.hunter, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class RefreshToken(Base, TimestampMixin):
    """Hashed refresh tokens, rotated on use, revocable."""

    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = pk()
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user|va
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

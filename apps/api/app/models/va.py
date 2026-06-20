"""va — Virtual Assistant identity (separate principal, not a User)."""

import uuid

from sqlalchemy import Boolean, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Track
from app.db import Base
from app.models.base import TimestampMixin, pk


class Va(Base, TimestampMixin):
    __tablename__ = "va"

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp_jid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

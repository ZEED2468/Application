"""Shared model base, mixins, and column helpers.

Uses sqlalchemy.Uuid so the schema is portable (UUID on Postgres, CHAR on
SQLite) — the test suite runs against SQLite, production against Postgres.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_id


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=new_id)


def user_fk(*, index: bool = True) -> Mapped[uuid.UUID]:
    """`user_id` foreign key present on every hunter-owned row."""
    return mapped_column(
        Uuid, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=index
    )

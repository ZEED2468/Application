"""platform — a named label an admin is attached to.

Lightweight (not a tenant): hunters/jobs/domains are NOT partitioned by platform.
A super-admin manages platforms and all admins; a platform-admin is scoped to the
platform on their `user.platform_id`.
"""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk


class Platform(Base, TimestampMixin):
    __tablename__ = "platform"

    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

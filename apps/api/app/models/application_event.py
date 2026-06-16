"""application_event — the per-application audit/activity trail.

Every state change (created via auto|manual, CV generated, submitted, status
changed by VA, reply received) writes one row, so the dashboard can show a full
history and no path can mutate an application invisibly.
"""

import uuid

from sqlalchemy import ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class ApplicationEvent(Base, TimestampMixin):
    __tablename__ = "application_event"
    __table_args__ = (Index("ix_app_event_app_created", "application_id", "created_at"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("application.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False)  # created|cv_generated|...
    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    detail: Mapped[dict] = mapped_column(JsonB, default=dict)

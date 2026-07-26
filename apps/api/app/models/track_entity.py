"""track — a first-class, user-created career track (R: track readiness).

A Track is the lifecycle/registry layer on top of the existing per-(user, track)
data: its `slug` is the track key used everywhere else (MasterProfile.track,
RoleCv.track, Job.track — the enum value or a custom string). Readiness (ready vs
setup_required) is DERIVED from whether a source CV exists for the slug; `archived_at`
is the only stored lifecycle state. A track is "incomplete" until it has a CV.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class Track(Base, TimestampMixin):
    __tablename__ = "track"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_track_user_slug"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    # The track key used across the platform (enum value or a custom string).
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)  # display name
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

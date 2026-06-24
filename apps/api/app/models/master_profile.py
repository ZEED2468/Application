"""master_profile — per (user, track) structured CV data + truth corpus."""

import uuid

from sqlalchemy import Boolean, Enum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.enums import Track
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk

# JSONB on Postgres, JSON elsewhere (SQLite tests).
JsonB = JSON().with_variant(JSONB(), "postgresql")


class MasterProfile(Base, TimestampMixin):
    __tablename__ = "master_profile"
    __table_args__ = (UniqueConstraint("user_id", "track", name="uq_profile_user_track"),)

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    track: Mapped[Track] = mapped_column(Enum(Track, native_enum=False), nullable=False)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[dict] = mapped_column(JsonB, default=dict)
    experience: Mapped[list] = mapped_column(JsonB, default=list)
    education: Mapped[list] = mapped_column(JsonB, default=list)
    projects: Mapped[list] = mapped_column(JsonB, default=list)
    links: Mapped[dict] = mapped_column(JsonB, default=dict)
    # Explicit job titles the hunter wants — discovery filters scraped jobs to these.
    target_roles: Mapped[list] = mapped_column(JsonB, default=list)
    # Ground truth that bounds tailoring — the LLM may only reframe what is here.
    truth_corpus: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

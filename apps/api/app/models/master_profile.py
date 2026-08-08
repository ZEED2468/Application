"""master_profile — per (user, track) structured CV data + truth corpus."""

import uuid

from sqlalchemy import Boolean, Enum, String, Text, UniqueConstraint
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
    # Structured, user-verified knowledge NOT on the uploaded CV (frameworks, tools,
    # certifications, open-source, side projects, languages, …). Category -> list[str].
    # Part of the truth corpus: generation may reference it only because the user
    # asserts it is genuinely true.
    verified_extras: Mapped[dict] = mapped_column(JsonB, default=dict)
    # Per-track career preferences (R3): skills to emphasize + freeform prefs.
    preferred_skills: Mapped[list] = mapped_column(JsonB, default=list)
    career_preferences: Mapped[dict] = mapped_column(JsonB, default=dict)
    # Career Workspace details (R8). links (linkedin/github/portfolio) reuse `links`.
    preferred_locations: Mapped[list] = mapped_column(JsonB, default=list)
    preferred_job_types: Mapped[list] = mapped_column(JsonB, default=list)
    salary_expectation: Mapped[dict] = mapped_column(JsonB, default=dict)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # The CV-engine template bound for this track (a built-in id or a cv_template ref;
    # NULL → the canonical default). Resolved by templates.resolve.
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

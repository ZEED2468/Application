"""ats_analysis — a persisted, versioned ATS check result.

Replaces the fragile `sessionStorage` handoff between the ATS checker and the LaTeX
builder: a first-class feature does not talk to the rest of the app through browser
storage. Each `/ats/check` appends a row (immutable history, newest = current), keyed
to a job (nullable — the checker also runs standalone, before onboarding). Stores the
gate result, the consolidated score, the full breakdown (criticals matched/missing,
supporting coverage, retracted false-positives, stretch) and the AI corrections +
recommendations, plus whether the AI layer was live for that run.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class AtsAnalysis(Base, TimestampMixin):
    __tablename__ = "ats_analysis"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    # Null when the check ran standalone (no job binding) — the top-of-funnel path.
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="CASCADE"), nullable=True, index=True
    )
    track: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Structural parseability of the rendered artifact: pass | fail | unevaluated.
    gate_status: Mapped[str] = mapped_column(String(16), default="unevaluated", nullable=False)
    # Consolidated content-readiness number; NULL when the gate failed (a fix-first state).
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # The full ats.score() breakdown (criticals, coverage, matched/missing, stretch, …).
    breakdown: Mapped[dict] = mapped_column(JsonB, default=dict)
    # The AI analysis dict (recommendations / gaps / false_positives / verdict); NULL if AI off.
    ai: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    ai_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Monotonic per (user, job) run counter; newest row is the current analysis.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Which rendered artifact the gate inspected (filled once the format gate lands).
    artifact_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)

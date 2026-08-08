"""cv_run / cv_run_step — the pipeline's persisted state machine.

`CvRun` is one pass of a CV through the pipeline; `CvRunStep` records every
transition (state, input hash, violations, duration, and — once LLM steps land —
model + prompt_version). Together they give resumability, an audit trail
("why did it change this?"), token-cost accounting, and free eval pairs.

Everything reproducible is pinned per run at creation (invariant #10): the rule
`registry_version`, the `(template_id, template_version)`, and a `ledger_snapshot`
that isolates the run from concurrent profile edits. `score` is nullable and NULL
whenever the format gate failed — a failed compile never carries a number (the
same honesty rule as `ats_analysis.score`).

Modeled on `ats_analysis` (versioned, immutable, JsonB, portable `native_enum=False`
enums so the sqlite test DB works).
"""

import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import RunMode, RunState
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class CvRun(Base, TimestampMixin):
    __tablename__ = "cv_run"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    # Null for a standalone run (POST /cv/runs); set when a run is scoped to a job.
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="CASCADE"), nullable=True, index=True
    )
    state: Mapped[RunState] = mapped_column(
        Enum(RunState, native_enum=False), default=RunState.ingested, nullable=False
    )
    mode: Mapped[RunMode] = mapped_column(
        Enum(RunMode, native_enum=False), default=RunMode.fresh_build, nullable=False
    )
    # The run input: {cv_json, jd_text, role_title, track}.
    input: Mapped[dict] = mapped_column(JsonB, default=dict)
    # The closed set of truths content may draw from — snapshotted per run (invariant #10).
    ledger_snapshot: Mapped[dict] = mapped_column(JsonB, default=dict)
    # Pins: which rule set and template produced this run (attributable deltas).
    registry_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Consolidated content-readiness number; NULL when the gate failed (a fix-first state).
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # The final violation set (list of Violation dicts) after re-diagnosis.
    violations: Mapped[list] = mapped_column(JsonB, default=list)
    # Per-rule fail→pass / pass→fail transitions across the run (the delta report).
    delta: Mapped[dict] = mapped_column(JsonB, default=dict)
    # Advisory LLM read on the verified artifact (Slice 6): semantic JD coverage + a fit
    # verdict. NULL offline / when no JD is attached. Never feeds the score or the release
    # decision — judgment is second, on the deterministic floor.
    judgment: Mapped[dict | None] = mapped_column(JsonB, nullable=True)
    # R2 key of the compiled PDF (filled once RENDER succeeds).
    artifact_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)


class CvRunStep(Base, TimestampMixin):
    __tablename__ = "cv_run_step"

    id: Mapped[uuid.UUID] = pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cv_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = user_fk()
    # The state this step transitioned the run into.
    state: Mapped[RunState] = mapped_column(
        Enum(RunState, native_enum=False), nullable=False
    )
    # Hash of the step's input — resume can skip a step whose input is unchanged.
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Violations observed at this step (before/after a transition's effect).
    violations: Mapped[list] = mapped_column(JsonB, default=list)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Filled only when an LLM was involved (later slices) — audit + token accounting.
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Free-form step context (gap verdicts, gate flags, extractor disagreements, …).
    detail: Mapped[dict] = mapped_column(JsonB, default=dict)

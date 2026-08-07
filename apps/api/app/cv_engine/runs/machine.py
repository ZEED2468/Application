"""The pipeline as a recorded, synchronous state machine.

One coordinator runs the transitions in order; each is a discrete step that mutates the
run's state and persists a `CvRunStep` (audit trail + resumability + cost slots). The
transitions are written as small idempotent units over `(session, run, work)`, so
converting each into a Celery task later (suspend/resume, Slice 7) is mechanical — the
only thing that would change is persisting/reloading the in-memory `work` between steps.

Flow (Slice 1, no PATCH round yet):
    INGESTED → GAP_ANALYZED → DIAGNOSED → RECOMPILED → VERIFIED → RELEASED
                                                              ↘ NEEDS_REVIEW (terminal, visible)

Terminal honesty: a run is RELEASED only when the format gate PASSED on a real compiled
PDF and no critical/major violation remains. A missing compiler (gate ``unevaluated``),
a failed compile, or any blocking violation ends at NEEDS_REVIEW — never a silent pass.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

from app.core.enums import RunMode, RunState
from app.cv_engine.fixes.deterministic import FIX_MAP, tidy_links
from app.cv_engine.ingest import build_ledger
from app.cv_engine.render.compile import CompileResult, compile_tex
from app.cv_engine.render.extract import dual_extract
from app.cv_engine.rules import default_registry
from app.cv_engine.rules.base import Phase, Registry, RuleContext, Violation, is_blocking
from app.cv_engine.runs.models import CvRun, CvRunStep
from app.cv_engine.scoring import score_artifact
from app.integrations import r2
from app.pipelines.apply import format_gate
from app.pipelines.apply.render import build_tex

DEFAULT_TEMPLATE_ID = "canonical"
DEFAULT_TEMPLATE_VERSION = 1
# The canonical template's required slots (the mold's demand). The full TemplateSpec /
# slot manifest lands in Slice 4; here the default template's demand is fixed.
REQUIRED_SLOTS = ("summary", "experience", "skills", "contact")


@dataclass
class _Work:
    """In-memory intermediates threaded between transitions (persisted via steps/run)."""

    input: dict
    registry: Registry
    ledger: list[dict] = field(default_factory=list)
    tex: str | None = None
    compiled: CompileResult | None = None
    extract_a: str = ""
    extract_b: str = ""
    gate: dict | None = None
    breakdown: dict | None = None
    draft_violations: list[Violation] = field(default_factory=list)
    rendered_violations: list[Violation] = field(default_factory=list)
    patch: dict = field(default_factory=lambda: {"fixed": [], "resolved": []})

    @property
    def cv_json(self) -> dict:
        return self.input.get("cv_json") or {}

    @property
    def name(self) -> str:
        return str(self.input.get("name") or "")

    @property
    def extracted_text(self) -> str:
        return self.extract_a or self.extract_b


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


async def _record(
    session, run: CvRun, state: RunState, *, violations=None, detail=None,
    duration_ms=None, input_hash=None,
) -> CvRunStep:
    step = CvRunStep(
        run_id=run.id, user_id=run.user_id, state=state,
        violations=[v.to_dict() for v in (violations or [])],
        detail=detail or {}, duration_ms=duration_ms, input_hash=input_hash,
    )
    session.add(step)
    run.state = state
    await session.flush()
    return step


def _draft_ctx(work: _Work) -> RuleContext:
    return RuleContext(
        cv_json=work.cv_json, ledger=work.ledger, jd_text=work.input.get("jd_text") or "",
        role_title=work.input.get("role_title"), track=work.input.get("track"),
        name=work.name,
    )


def _rendered_ctx(work: _Work) -> RuleContext:
    ctx = _draft_ctx(work)
    ctx.tex = work.tex
    ctx.pdf = work.compiled.pdf if work.compiled else None
    ctx.extract_a = work.extract_a
    ctx.extract_b = work.extract_b
    ctx.extracted_text = work.extracted_text
    ctx.gate = work.gate
    ctx.ats_breakdown = work.breakdown
    return ctx


# --- Transitions --------------------------------------------------------------------


async def _ingest(session, run: CvRun, work: _Work) -> None:
    t = time.perf_counter()
    work.ledger = build_ledger(work.input)
    run.ledger_snapshot = {"facts": work.ledger}
    await _record(
        session, run, RunState.ingested,
        detail={"fact_count": len(work.ledger)},
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


async def _gap_analyze(session, run: CvRun, work: _Work) -> None:
    """Record slot verdicts against the canonical template's required slots.

    Deterministic pass only (FILLED vs TRUE_GAP). INFERABLE (LLM selection) and the
    NEEDS_INPUT suspension for TRUE_GAPs land in Slice 7 — here a missing required slot
    simply surfaces as a structure violation downstream, so the run stays linear.
    """
    t = time.perf_counter()
    cv = work.cv_json
    filled = {
        "summary": bool((cv.get("summary") or "").strip()),
        "experience": bool(cv.get("experience")),
        "skills": bool(cv.get("skills")),
        "contact": any(str(v).strip() for v in (cv.get("links") or {}).values()),
    }
    verdicts = {s: ("FILLED" if filled.get(s) else "TRUE_GAP") for s in REQUIRED_SLOTS}
    await _record(
        session, run, RunState.gap_analyzed, detail={"slots": verdicts},
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


async def _diagnose(session, run: CvRun, work: _Work) -> None:
    t = time.perf_counter()
    work.draft_violations = work.registry.run(_draft_ctx(work), Phase.draft)
    await _record(
        session, run, RunState.diagnosed, violations=work.draft_violations,
        input_hash=_hash(work.cv_json),
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


async def _patch(session, run: CvRun, work: _Work) -> None:
    """Apply deterministic, zero-LLM fixes; re-diagnose the draft to record the fail→pass delta.

    Rule-driven: for each fixable rule that fired, run its mapped transform; plus link hygiene.
    Every fix is grounding-safe (reformat/trim only), so the same ledger still bounds the run.
    """
    t = time.perf_counter()
    pre_ids = {v.rule_id for v in work.draft_violations}
    cv = work.cv_json
    fixes: list[dict] = []
    for rule_id, fix_fn in FIX_MAP.items():
        if rule_id in pre_ids:
            cv, applied = fix_fn(cv)
            fixes.extend(applied)
    cv, applied = tidy_links(cv)  # link hygiene has no dedicated rule
    fixes.extend(applied)
    work.input["cv_json"] = cv

    work.draft_violations = work.registry.run(_draft_ctx(work), Phase.draft)
    resolved = sorted(pre_ids - {v.rule_id for v in work.draft_violations})
    work.patch = {"fixed": fixes, "resolved": resolved}
    await _record(
        session, run, RunState.patching, violations=work.draft_violations,
        detail={"fixed_count": len(fixes), "resolved": resolved},
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


async def _render(session, run: CvRun, work: _Work) -> None:
    t = time.perf_counter()
    work.tex = build_tex(work.cv_json, name=work.name)
    work.compiled = await compile_tex(work.tex)
    pdf = work.compiled.pdf
    if pdf:
        key = f"{run.user_id}/cv-run/{run.id}/cv.pdf"
        await r2.put_bytes(key, pdf, "application/pdf")
        run.artifact_ref = key
        work.extract_a, work.extract_b = dual_extract(pdf)
    await _record(
        session, run, RunState.recompiled,
        detail={
            "has_compiler": work.compiled.has_compiler,
            "compiled": pdf is not None,
            "bytes": len(pdf or b""),
            "stderr": (work.compiled.stderr or "")[:500],
        },
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


async def _re_diagnose(session, run: CvRun, work: _Work) -> None:
    """Verify on the REAL artifact: gate + rendered rules on re-extracted text + score."""
    t = time.perf_counter()
    c = work.compiled
    gate = format_gate.evaluate(
        tex=work.tex, pdf=(c.pdf if c else None),
        has_compiler=(c.has_compiler if c else False),
    )
    work.gate = gate
    if gate["status"] == "unevaluated":
        # No artifact could be measured — no number, no rendered checks (invariant #2).
        run.score = None
        work.rendered_violations = []
    else:
        work.rendered_violations = work.registry.run(_rendered_ctx(work), Phase.rendered)
        work.breakdown = score_artifact(
            extracted_text=work.extracted_text,
            jd_text=work.input.get("jd_text") or "",
            role_title=work.input.get("role_title"), gate=gate,
        )
        run.score = work.breakdown.get("score")
    await _record(
        session, run, RunState.verified, violations=work.rendered_violations,
        detail={"gate": gate, "score": run.score},
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


def _delta(final: list[Violation]) -> dict:
    """Per-rule end-state (the delta report seed; fail→pass tracking arrives with PATCH)."""
    failed = sorted({v.rule_id for v in final})
    blocking = sorted({v.rule_id for v in final if is_blocking(v.severity)})
    return {"failed": failed, "blocking": blocking, "violation_count": len(final)}


async def _release(session, run: CvRun, work: _Work) -> None:
    t = time.perf_counter()
    final = [*work.draft_violations, *work.rendered_violations]
    run.violations = [v.to_dict() for v in final]
    run.delta = {**work.patch, **_delta(final)}
    blocking = any(is_blocking(v.severity) for v in final)
    gate_passed = bool(work.gate and work.gate.get("status") == "pass")
    state = RunState.released if (gate_passed and not blocking) else RunState.needs_review
    await _record(
        session, run, state, violations=final,
        detail={
            "gate_status": (work.gate or {}).get("status"),
            "blocking": blocking, "score": run.score,
        },
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


# --- Public API ---------------------------------------------------------------------


async def create_run(
    session, *, user_id, input: dict, mode: RunMode = RunMode.fresh_build, job_id=None,
) -> CvRun:
    """Create a pinned run row (state INGESTED). Pins: registry version + template + input."""
    registry = default_registry()
    run = CvRun(
        user_id=user_id, job_id=job_id, state=RunState.ingested, mode=mode, input=input,
        registry_version=registry.version(),
        template_id=DEFAULT_TEMPLATE_ID, template_version=DEFAULT_TEMPLATE_VERSION,
        violations=[], delta={},
    )
    session.add(run)
    await session.flush()
    return run


async def coordinate(session, run: CvRun) -> CvRun:
    """Run the pipeline to a terminal state (RELEASED / NEEDS_REVIEW), recording each step."""
    work = _Work(input=run.input or {}, registry=default_registry())
    await _ingest(session, run, work)
    await _gap_analyze(session, run, work)
    await _diagnose(session, run, work)
    await _patch(session, run, work)
    await _render(session, run, work)
    await _re_diagnose(session, run, work)
    await _release(session, run, work)
    return run


async def run_pipeline(
    session, *, user_id, input: dict, mode: RunMode = RunMode.fresh_build, job_id=None,
) -> CvRun:
    """Create + coordinate a run in one call (the endpoint + tests use this)."""
    run = await create_run(session, user_id=user_id, input=input, mode=mode, job_id=job_id)
    return await coordinate(session, run)

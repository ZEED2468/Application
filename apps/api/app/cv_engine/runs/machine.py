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

import copy
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
from app.cv_engine.rules.base import FixMode, Phase, Registry, RuleContext, Violation, is_blocking
from app.cv_engine.runs import gaps
from app.cv_engine.runs.models import CvRun, CvRunStep
from app.cv_engine.scoring import score_artifact
from app.cv_engine.templates import (
    TemplateSpec,
    default_template,
    get_template,
    render_template,
    resolve_template,
)
from app.cv_engine.templates.library import slot_present
from app.integrations import r2
from app.pipelines.apply import format_gate

MAX_REPAIR_ROUNDS = 2   # bounded agent repair per run (spec §5)
MAX_PAGE_ROUNDS = 1     # one extra render round to trim to the page limit


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
    spec: TemplateSpec | None = None
    suspended: bool = False   # set by _gap_analyze when the run stops for a TRUE_GAP (Slice 7)

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
    duration_ms=None, input_hash=None, model=None, prompt_version=None,
) -> CvRunStep:
    step = CvRunStep(
        run_id=run.id, user_id=run.user_id, state=state,
        violations=[v.to_dict() for v in (violations or [])],
        detail=detail or {}, duration_ms=duration_ms, input_hash=input_hash,
        model=model, prompt_version=prompt_version,
    )
    session.add(step)
    run.state = state
    await session.flush()
    return step


def _draft_ctx(work: _Work) -> RuleContext:
    return RuleContext(
        cv_json=work.cv_json, ledger=work.ledger, jd_text=work.input.get("jd_text") or "",
        role_title=work.input.get("role_title"), track=work.input.get("track"),
        name=work.name, spec=work.spec,
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


async def _infer_slots(work: _Work) -> dict:
    """Fill an INFERABLE slot (the summary) from the ledger, behind the deterministic grounding
    seal (door #1) AND an independent supports judge (door #2). A no-op offline or on rejection.
    Splices the summary into work.cv_json; returns audit meta for the gap step."""
    from app.llm import client

    meta = {"model": None, "prompt_version": None, "inferred": []}
    if not client.is_live("cv_infer") or slot_present("summary", work.cv_json):
        return meta
    from app.llm import cv_infer

    result = await cv_infer.infer_summary(
        work.ledger, role_title=work.input.get("role_title"),
        jd_text=work.input.get("jd_text") or "",
    )
    if not result.applied or not result.summary:
        return meta

    # Door #1: the grounding seal — reject a summary that introduces any blocking violation.
    candidate = {**work.cv_json, "summary": result.summary}
    pre_block = {v.rule_id for v in work.registry.run(_draft_ctx(work), Phase.draft)
                 if is_blocking(v.severity)}
    cand_ctx = _draft_ctx(_Work(input={**work.input, "cv_json": candidate},
                                registry=work.registry, ledger=work.ledger, spec=work.spec))
    cand_block = {v.rule_id for v in work.registry.run(cand_ctx, Phase.draft)
                  if is_blocking(v.severity)}
    if cand_block - pre_block:
        return meta

    # Door #2: independent verifier — every claim/entity is in the candidate's history.
    ledger_text = " ".join(str(f.get("text") or "") for f in work.ledger)
    if not await cv_infer.supports(result.summary, ledger_text):
        return meta

    work.input["cv_json"] = candidate
    meta.update(model=result.model, prompt_version=cv_infer.PROMPT_VERSION, inferred=["summary"])
    return meta


async def _gap_analyze(session, run: CvRun, work: _Work) -> None:
    """Classify the template's REQUIRED slots (FILLED / INFERABLE / TRUE_GAP), fill what is
    inferable from the ledger, and SUSPEND to NEEDS_INPUT for genuine gaps (Slice 7).

    An absent-but-derivable slot (the summary) is composed from the candidate's own history,
    verified, and filled — the run continues. An absent, non-inferable required slot raises real
    prompt-cards on a ChatSession linked to the run and stops the pipeline; answering them (via the
    existing /chat endpoint) resumes it. Offline, inference no-ops and only the deterministic
    TRUE_GAP suspension applies, so a complete CV runs exactly as before.
    """
    t = time.perf_counter()
    verdicts = gaps.classify(work.spec, work.cv_json)
    infer = await _infer_slots(work)
    slots = gaps.gap_slots(work.spec, work.cv_json)
    detail = {"slots": verdicts, "template": work.spec.id if work.spec else None}
    if infer["inferred"]:
        detail["inferred"] = infer["inferred"]
    if slots:
        chat = await gaps.raise_gap_prompts(session, run, slots)
        run.needs_input = {"session_id": str(chat.id), "slots": slots}
        work.suspended = True
        await _record(
            session, run, RunState.needs_input,
            detail={**detail, "gaps": slots, "session_id": str(chat.id)},
            model=infer["model"], prompt_version=infer["prompt_version"],
            duration_ms=int((time.perf_counter() - t) * 1000),
        )
        return
    run.needs_input = None
    await _record(
        session, run, RunState.gap_analyzed, detail=detail,
        model=infer["model"], prompt_version=infer["prompt_version"],
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

    # Bounded agent repair behind the deterministic floor (LLM; a no-op offline).
    repair = await _agent_repair_draft(work, fixes)

    resolved = sorted(pre_ids - {v.rule_id for v in work.draft_violations})
    work.patch = {"fixed": fixes, "resolved": resolved}
    await _record(
        session, run, RunState.patching, violations=work.draft_violations,
        detail={"fixed_count": len(fixes), "resolved": resolved, **repair["detail"]},
        model=repair["model"], prompt_version=repair["prompt_version"],
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


def _apply_rewrites(
    cv_json: dict, bullets: list[dict], summary: str | None
) -> tuple[dict, list[dict]]:
    """Splice ONLY the confirmed rewrites (change nothing else); return (cv, FixRecords)."""
    cv = copy.deepcopy(cv_json)
    records: list[dict] = []
    rewrite_map = {b["original"]: b["rewrite"] for b in bullets if b["rewrite"] != b["original"]}
    for e in cv.get("experience") or []:
        if not isinstance(e, dict) or not e.get("bullets"):
            continue
        new: list = []
        for b in e["bullets"]:
            after = rewrite_map.get(str(b))
            if after:
                records.append({"rule_id": "agent.rewrite_bullet", "field": "experience.bullets",
                                "before": str(b), "after": after})
                new.append(after)
            else:
                new.append(b)
        e["bullets"] = new
    if summary and not (cv.get("summary") or "").strip():
        records.append({"rule_id": "agent.write_summary", "field": "summary",
                        "before": "", "after": summary})
        cv["summary"] = summary
    return cv, records


async def _agent_repair_draft(work: _Work, fixes: list[dict]) -> dict:
    """Bounded LLM rewrite of agent-fixable draft violations. Each rewrite must pass an
    independent entailment judge AND the deterministic grounding seal (re-diagnose); a round
    that introduces a blocking violation is rejected. Returns audit meta for the patch step."""
    from app.llm import client

    meta = {"model": None, "prompt_version": None, "detail": {}}
    if not client.is_live("cv_repair"):
        return meta
    from app.llm import cv_repair

    rounds: list[dict] = []
    model: str | None = None
    for attempt in range(MAX_REPAIR_ROUNDS):
        agent_viol = [v for v in work.draft_violations
                      if work.registry.fix_mode_of(v.rule_id) is FixMode.agent]
        if not agent_viol:
            break
        result = await cv_repair.repair_draft(
            work.cv_json, agent_viol, work.ledger,
            work.registry.constraints_block(_draft_ctx(work), Phase.draft),
            jd_text=work.input.get("jd_text") or "",
        )
        if not result.applied:
            break
        model = result.model or model

        # Door #2: independent judge confirms each bullet rewrite adds no claim (drop unconfirmed).
        kept = [b for b in (result.rewrites.get("bullets") or [])
                if await cv_repair.entails(b["original"], b["rewrite"])]
        summary = result.rewrites.get("summary")
        if not kept and not summary:
            rounds.append({"attempt": attempt, "accepted": False,
                           "reason": "no_confirmed_rewrites"})
            break

        candidate, records = _apply_rewrites(work.cv_json, kept, summary)
        cand_ctx = _draft_ctx(_Work(input={**work.input, "cv_json": candidate},
                                    registry=work.registry, ledger=work.ledger, spec=work.spec))
        cand_viol = work.registry.run(cand_ctx, Phase.draft)

        # Door #5: the deterministic seal — reject a round that introduces any blocking violation.
        pre_block = {v.rule_id for v in work.draft_violations if is_blocking(v.severity)}
        new_block = {v.rule_id for v in cand_viol if is_blocking(v.severity)} - pre_block
        if new_block:
            rounds.append({"attempt": attempt, "accepted": False,
                           "reason": "introduced_blocking", "rules": sorted(new_block)})
            break

        work.input["cv_json"] = candidate
        work.draft_violations = cand_viol
        fixes.extend(records)
        rounds.append({"attempt": attempt, "accepted": True,
                       "bullets": len(kept), "summary": bool(summary)})
        # Stop if no progress on the agent-fixable set.
        still = sum(1 for v in cand_viol if work.registry.fix_mode_of(v.rule_id) is FixMode.agent)
        if still >= len(agent_viol):
            break

    meta["model"] = model
    meta["prompt_version"] = cv_repair.PROMPT_VERSION if rounds else None
    meta["detail"] = {"repair_rounds": rounds} if rounds else {}
    return meta


async def _render(session, run: CvRun, work: _Work) -> None:
    t = time.perf_counter()
    work.tex = render_template(work.spec, work.cv_json, name=work.name)
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


def _leaves(x, out: set | None = None) -> set:
    out = set() if out is None else out
    if isinstance(x, str):
        s = x.strip()
        if s:
            out.add(s)
    elif isinstance(x, dict):
        for v in x.values():
            _leaves(v, out)
    elif isinstance(x, list):
        for v in x:
            _leaves(v, out)
    return out


async def _page_fit(session, run: CvRun, work: _Work) -> None:
    """Outer trim loop: if the rendered CV exceeds the template's page limit, let the agent
    REMOVE the lowest-relevance content (subset-verified — removal never invents), then
    re-render + re-verify. Bounded; a no-op offline or when it doesn't over-run."""
    from app.llm import client

    if not work.spec or not client.is_live("cv_repair"):
        return
    from app.llm import cv_repair

    for _ in range(MAX_PAGE_ROUNDS):
        if not any(v.rule_id == "rendered.page_count" for v in work.rendered_violations):
            return
        t = time.perf_counter()
        result = await cv_repair.trim_to_fit(
            work.cv_json, work.spec.page_limit, jd_text=work.input.get("jd_text") or "",
        )
        # Removal-only: every leaf in the trimmed CV must already exist in the original.
        if (not result.applied or not result.cv_json
                or not _leaves(result.cv_json) <= _leaves(work.cv_json)):
            return
        work.input["cv_json"] = result.cv_json
        work.patch.setdefault("fixed", []).append(
            {"rule_id": "agent.trim_to_fit", "field": "cv_json",
             "before": "over the page limit", "after": f"trimmed to fit {work.spec.page_limit}"}
        )
        work.draft_violations = work.registry.run(_draft_ctx(work), Phase.draft)
        await _record(
            session, run, RunState.patching, model=result.model,
            prompt_version=cv_repair.PROMPT_VERSION,
            detail={"page_fit": True, "page_limit": work.spec.page_limit},
            duration_ms=int((time.perf_counter() - t) * 1000),
        )
        await _render(session, run, work)
        await _re_diagnose(session, run, work)


async def _judge(session, run: CvRun, work: _Work) -> None:
    """Advisory LLM judgment on the verified artifact — second, on the deterministic floor.

    Slice 6. Rescues JD terms the exact-keyword scan missed, each backed by a verbatim quote
    (door #1) and confirmed by an independent skeptical verifier (door #2); adds an advisory fit
    verdict (reusing ats_analyze). Writes `run.judgment` ONLY — never the score, the violations, or
    the release decision. A no-op offline, without a JD, or when there is no artifact text."""
    from app.llm import client

    jd_text = (work.input.get("jd_text") or "").strip()
    cv_text = work.extracted_text
    if not work.breakdown or not jd_text or not cv_text.strip():
        return
    if not (client.is_live("cv_judge") or client.is_live("ats_analyze")):
        return
    from app.llm import ats_analyze, cv_judge

    t = time.perf_counter()
    role_title = work.input.get("role_title")
    det_missing = list(dict.fromkeys([
        *(work.breakdown.get("missing_critical") or []),
        *(work.breakdown.get("missing_keywords") or []),
    ]))
    pool = set(det_missing)

    # Semantic coverage rescue — two doors: verbatim evidence (door #1) + a skeptical verifier.
    result = await cv_judge.rescue_coverage(
        cv_text, work.breakdown, jd_text=jd_text, role_title=role_title,
    )
    rescued: list[dict] = []
    for r in result.rescues:
        # Pool guard + door #1 (verbatim quote) BEFORE spending a verifier call on door #2.
        if r["keyword"] not in pool:
            continue
        if not cv_judge.evidence_present(r["evidence"], cv_text):
            continue
        if not await cv_judge.confirms(r["keyword"], r["evidence"]):
            continue
        rescued.append(r)
    covered = {r["keyword"] for r in rescued}
    still_missing = [k for k in det_missing if k not in covered]

    # Advisory fit verdict — the existing ats_analyze facade (its own offline-safe fallback inside).
    analysis = await ats_analyze.analyze(
        cv_text=cv_text, jd_text=jd_text, role_title=role_title or "",
        rule_score=run.score or 0.0, breakdown=work.breakdown,
    )

    run.judgment = {
        "coverage": {
            "deterministic_missing": det_missing,
            "semantic_covered": rescued,
            "still_missing": still_missing,
            "summary": (
                f"{len(rescued)}/{len(det_missing)} keyword-missed term(s) covered under "
                f"another name; {len(still_missing)} genuinely missing."
            ),
        },
        "fit": ats_analyze.analysis_to_dict(analysis),
        "model": result.model,
        "prompt_version": cv_judge.PROMPT_VERSION,
    }
    await _record(
        session, run, RunState.judged, model=result.model,
        prompt_version=cv_judge.PROMPT_VERSION,
        detail={"rescued": sorted(covered), "still_missing_count": len(still_missing)},
        duration_ms=int((time.perf_counter() - t) * 1000),
    )


# --- Public API ---------------------------------------------------------------------


async def create_run(
    session, *, user_id, input: dict, mode: RunMode = RunMode.fresh_build, job_id=None,
    spec: TemplateSpec | None = None,
) -> CvRun:
    """Create a pinned run row (state INGESTED). Pins: registry version + template + input."""
    registry = default_registry()
    spec = spec or default_template()
    run = CvRun(
        user_id=user_id, job_id=job_id, state=RunState.ingested, mode=mode, input=input,
        registry_version=registry.version(),
        template_id=spec.id, template_version=spec.version,
        violations=[], delta={},
    )
    session.add(run)
    await session.flush()
    return run


async def coordinate(session, run: CvRun, *, spec: TemplateSpec | None = None) -> CvRun:
    """Run the pipeline to a terminal state (RELEASED / NEEDS_REVIEW), recording each step."""
    if spec is None:  # re-resolve the EXACT pinned template (immutable) if not threaded in
        spec = await get_template(session, run.template_id, run.template_version)
        spec = spec or default_template()
    work = _Work(input=run.input or {}, registry=default_registry(), spec=spec)
    await _ingest(session, run, work)
    await _gap_analyze(session, run, work)
    if work.suspended:                 # a TRUE_GAP stopped the run at NEEDS_INPUT (Slice 7)
        return run
    await _diagnose(session, run, work)
    await _patch(session, run, work)
    await _render(session, run, work)
    await _re_diagnose(session, run, work)
    await _page_fit(session, run, work)
    await _judge(session, run, work)
    await _release(session, run, work)
    return run


async def run_pipeline(
    session, *, user_id, input: dict, mode: RunMode = RunMode.fresh_build, job_id=None,
    template_ref: str | None = None,
) -> CvRun:
    """Create + coordinate a run in one call (the endpoint + tests use this)."""
    spec = await resolve_template(
        session, user_id=user_id, track=(input or {}).get("track"), ref=template_ref
    )
    run = await create_run(
        session, user_id=user_id, input=input, mode=mode, job_id=job_id, spec=spec
    )
    return await coordinate(session, run, spec=spec)

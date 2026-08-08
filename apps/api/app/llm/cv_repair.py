"""Agent repair — bounded, truth-safe LLM rewrites of failing CV content.

Mirrors the ats_vet/resume_intel facade: gate on `client.is_live`, call `try_complete_text`,
fence-tolerant parse, `None`/error → no-op. It NEVER decides safety itself — it returns
proposed rewrites; the engine re-verifies each with an independent judge (`entails`) AND the
deterministic grounding seal before keeping any. Offline (fake mode) every call is a no-op.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PROMPT_VERSION = "cv_repair.v1"
# Repair-time arbitration, stated in every prompt (spec §2.3).
CONFLICT_PRIORITY = "truthfulness > compilability > page limit > coverage > style"


@dataclass
class RepairResult:
    # {"summary": str|None, "bullets": [{original, rewrite}]}
    rewrites: dict = field(default_factory=dict)
    cv_json: dict | None = None                   # a trimmed cv_json (trim_to_fit)
    model: str | None = None
    applied: bool = False


def _parse_json(raw: str) -> dict:
    """Extract the outermost JSON object (tolerates ```json fences / surrounding prose)."""
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        raise ValueError("no JSON object in completion")
    return json.loads(m.group(0))


def _model(feature: str) -> str | None:
    from app.llm import config as llm_config
    return llm_config.resolve(feature).model


def _flagged(violations, cv_json: dict) -> dict:
    """The specific items the agent may rewrite: weak/first-person bullets + a missing summary."""
    from app.pipelines.apply.intel import _FIRST_PERSON, bullets_of

    ids = {v.rule_id for v in violations}
    bullets: set[str] = set()
    for v in violations:
        if v.rule_id == "structure.strong_verbs" and v.span and v.span.get("text"):
            bullets.add(str(v.span["text"]))
    if "structure.no_first_person" in ids:
        bullets.update(b for b in bullets_of(cv_json) if _FIRST_PERSON.search(b))
    hints = sorted({v.fix_hint for v in violations if v.fix_hint})
    return {
        "summary_needed": "structure.summary_present" in ids,
        "bullets": sorted(bullets)[:12],
        "hints": hints,
    }


async def repair_draft(
    cv_json: dict, violations, ledger, constraints: str, *, jd_text: str = ""
) -> RepairResult:
    """Propose rewrites for the flagged draft violations (no-op offline / on failure)."""
    from app.llm import client

    if not client.is_live("cv_repair"):
        return RepairResult(applied=False)
    flagged = _flagged(violations, cv_json)
    if not flagged["bullets"] and not flagged["summary_needed"]:
        return RepairResult(applied=False)

    system = (
        "You repair specific flaws in a CV WITHOUT inventing anything. Rewrite ONLY the flagged "
        "items. Keep every fact, number, employer, date, and skill exactly — reword and strengthen "
        "verbs, but add no claim, metric, or outcome not already there. If a required summary is "
        "missing, write a 2-3 line role-anchored summary using ONLY facts visible in the CV. "
        f"Resolve conflicts by this priority: {CONFLICT_PRIORITY}. "
        "Return JSON ONLY: {\"summary\": string|null, "
        "\"bullets\": [{\"original\": string, \"rewrite\": string}]}."
    )
    prompt = json.dumps({
        "constraints": constraints,
        "fix_hints": flagged["hints"],
        "flagged_bullets": flagged["bullets"],
        "write_summary": flagged["summary_needed"],
        "cv_context": {k: cv_json.get(k) for k in ("headline", "skills", "experience")},
        "job_description": jd_text[:2000],
    }, indent=2)

    raw = await client.try_complete_text(system, prompt, max_tokens=1600, feature="cv_repair")
    if raw is None:
        return RepairResult(applied=False)
    try:
        data = _parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        return RepairResult(applied=False)

    rewrites = {
        "summary": (str(data["summary"]).strip() if data.get("summary") else None)
        if flagged["summary_needed"] else None,
        "bullets": [
            {"original": str(b["original"]), "rewrite": str(b["rewrite"])}
            for b in (data.get("bullets") or [])
            if isinstance(b, dict) and b.get("original") and b.get("rewrite")
        ],
    }
    return RepairResult(rewrites=rewrites, model=_model("cv_repair"), applied=True)


async def entails(original: str, rewrite: str) -> bool:
    """Independent judge (door #2): is the REWRITE fully supported by the ORIGINAL?

    Sees only original + rewrite, never the generator's reasoning. Biased to false-negatives —
    anything it can't confirm (no judge configured, failure, unsure) is refuted (dropped)."""
    if str(original).strip() == str(rewrite).strip():
        return True
    from app.llm import client

    if not client.is_live("cv_repair_verify"):
        return False
    system = (
        "You are a strict fact-checker. The REWRITE is SUPPORTED only if it makes NO claim, "
        "number, employer, skill, date, or outcome not already in the ORIGINAL (rewording and "
        "stronger verbs are fine). If it adds anything, or you are unsure, it is NOT supported. "
        "Answer JSON ONLY: {\"supported\": true|false}."
    )
    prompt = json.dumps({"original": original, "rewrite": rewrite})
    raw = await client.try_complete_text(system, prompt, max_tokens=80, feature="cv_repair_verify")
    if raw is None:
        return False
    try:
        return _parse_json(raw).get("supported") is True
    except (ValueError, json.JSONDecodeError):
        return False


async def trim_to_fit(cv_json: dict, page_limit: int, *, jd_text: str = "") -> RepairResult:
    """Propose a trimmed cv_json (removal-only) to fit the page limit; no-op offline/on failure.

    The caller enforces that the result is a strict subset of the original content (removal never
    invents), so grounding stays trivially safe."""
    from app.llm import client

    if not client.is_live("cv_repair"):
        return RepairResult(applied=False)
    system = (
        f"Trim this CV to fit {page_limit} page(s) by REMOVING the lowest-relevance bullets and "
        "sections only. Never add, reword, or invent — keep the strongest, most job-relevant "
        f"content verbatim. Resolve conflicts by: {CONFLICT_PRIORITY}. Return JSON ONLY: the same "
        "cv_json shape with fewer items."
    )
    prompt = json.dumps(
        {"cv_json": cv_json, "page_limit": page_limit, "job_description": jd_text[:2000]}
    )
    raw = await client.try_complete_text(system, prompt, max_tokens=3000, feature="cv_repair")
    if raw is None:
        return RepairResult(applied=False)
    try:
        trimmed = _parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        return RepairResult(applied=False)
    return RepairResult(cv_json=trimmed, model=_model("cv_repair"), applied=True)

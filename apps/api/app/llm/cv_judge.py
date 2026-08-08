"""LLM judgment on top of the deterministic floor — JD-coverage rescue + a fit verdict.

Judgment SECOND: this module never touches the deterministic score, the violation set, or the
release decision. It rescues JD terms the exact-keyword scan missed (K8s->Kubernetes,
Postgres->PostgreSQL, "GitHub Actions"->CI/CD) — but only the ones it can back with a VERBATIM
quote from the CV (door #1, the caller's deterministic `evidence_present` check) that an
independent skeptical verifier confirms actually demonstrates the term (door #2, `confirms`).

Mirrors the cv_repair/ats_vet facade: gate on `client.is_live`, `try_complete_text`, fence-tolerant
parse, `None`/error -> no-op. Offline (fake mode) every call is a no-op, so the deterministic score
stands alone and no judgment is written.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PROMPT_VERSION = "cv_judge.v1"

_WS = re.compile(r"\s+")


@dataclass
class CoverageResult:
    # [{keyword, evidence}] — proposed rescues; the caller verifies each (doors #1 + #2).
    rescues: list[dict] = field(default_factory=list)
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


def evidence_present(evidence: str, cv_text: str) -> bool:
    """Door #1 (deterministic): the cited quote must appear verbatim in the CV.

    Whitespace-normalized + case-insensitive so trivial spacing differences don't reject a real
    quote — but a fabricated quote (text not in the CV) is dropped. No fabricated evidence lands."""
    needle = _WS.sub(" ", (evidence or "").strip().lower())
    haystack = _WS.sub(" ", (cv_text or "").lower())
    return bool(needle) and needle in haystack


async def rescue_coverage(
    cv_text: str, breakdown: dict, *, jd_text: str = "", role_title: str | None = None
) -> CoverageResult:
    """Propose semantic rescues for deterministically-missing JD terms (no-op offline/on failure).

    The model may only speak to terms the keyword scan marked MISSING (the caller enforces the pool
    again), and every proposal must carry a verbatim CV quote — the caller re-checks both."""
    from app.llm import client

    if not client.is_live("cv_judge"):
        return CoverageResult(applied=False)
    pool = list(dict.fromkeys([
        *(breakdown.get("missing_critical") or []),
        *(breakdown.get("missing_keywords") or []),
    ]))
    if not pool:
        return CoverageResult(applied=False)

    system = (
        "You audit whether a CV already demonstrates specific job-description skills under a "
        "DIFFERENT name — synonyms, abbreviations, or adjacent tooling (e.g. K8s for Kubernetes, "
        "Postgres for PostgreSQL, GitHub Actions for CI/CD). For each MISSING term you are given, "
        "decide whether the CV genuinely shows it. Return ONLY terms you can back with a VERBATIM "
        "quote copied exactly from the CV text — do not paraphrase the quote, invent nothing, and "
        "omit any term that is not truly demonstrated. Return JSON ONLY: "
        "{\"covered\": [{\"keyword\": string, \"evidence\": string}]}."
    )
    prompt = json.dumps({
        "missing_terms": pool[:40],
        "cv_text": cv_text[:12000],
        "job_description": jd_text[:2000],
        "role_title": role_title or "",
    }, indent=2)

    raw = await client.try_complete_text(system, prompt, max_tokens=1200, feature="cv_judge")
    if raw is None:
        return CoverageResult(applied=False)
    try:
        data = _parse_json(raw)
    except (ValueError, json.JSONDecodeError):
        return CoverageResult(applied=False)

    rescues = [
        {"keyword": str(c["keyword"]).strip(), "evidence": str(c["evidence"]).strip()}
        for c in (data.get("covered") or [])
        if isinstance(c, dict) and c.get("keyword") and c.get("evidence")
    ]
    return CoverageResult(rescues=rescues, model=_model("cv_judge"), applied=True)


async def confirms(keyword: str, evidence: str) -> bool:
    """Independent verifier (door #2): does the exact CV quote genuinely demonstrate the JD term?

    Sees only (keyword, evidence), never the rescuer's reasoning. Biased to false-negatives: no
    verifier, a failure, or an unsure answer all mean NOT demonstrated (the rescue is dropped)."""
    from app.llm import client

    if not client.is_live("cv_judge_verify"):
        return False
    system = (
        "You are a strict fact-checker. Decide whether the QUOTE from a CV genuinely demonstrates "
        "the SKILL. A synonym, abbreviation, or adjacent tool of the skill counts (e.g. K8s "
        "demonstrates Kubernetes). Vague, generic, or aspirational text does NOT. If the quote "
        "does not clearly demonstrate the skill, or you are unsure, it is NOT demonstrated. Answer "
        "JSON ONLY: {\"demonstrated\": true|false}."
    )
    prompt = json.dumps({"skill": keyword, "quote": evidence})
    raw = await client.try_complete_text(system, prompt, max_tokens=80, feature="cv_judge_verify")
    if raw is None:
        return False
    try:
        return _parse_json(raw).get("demonstrated") is True
    except (ValueError, json.JSONDecodeError):
        return False

"""Advisory Resume-Intelligence pass — bullet coaching (PAR/XYZ), summary review, and
skills alignment.

Mirrors `ats_vet`: an offline-deterministic result plus an optional live-LLM pass that
returns **suggestions the human verifies**, never auto-applied text. Because reworded
bullets/summaries cannot pass the exact-substring truth guard, this output is kept off
that path entirely — it is advice, constrained by the prompt to the CV's real facts +
the verified truth-corpus terms. Uses the shared `resume_intel` feature (reuses the ATS
model config).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.pipelines.apply import ats, intel, verbs


@dataclass(slots=True)
class ResumeIntel:
    bullet_coaching: list[dict] = field(default_factory=list)
    summary_review: dict = field(default_factory=dict)
    skills_alignment: dict = field(default_factory=dict)
    powered: bool = False


def _offline(*, cv_json: dict, breakdown: dict, structure: dict, verified_terms: list[str] | None) -> ResumeIntel:
    bl = intel.bullets_of(cv_json)
    coaching: list[dict] = []
    for w in verbs.detect(bl)[:8]:
        coaching.append({
            "original": w["bullet"],
            "framework": "verb",
            "suggestion": f"Open with a stronger verb (e.g. '{w['suggestions'][0]}') if it accurately describes your role.",
        })
    for b in bl:
        if len(coaching) >= 12:
            break
        if not re.search(r"\d", b) and len(b.split()) >= 6:
            coaching.append({
                "original": b,
                "framework": "XYZ",
                "suggestion": "Add the result and how it was measured (accomplished X, measured by Y) — only if the number is real.",
            })

    matched = breakdown.get("matched_keywords", [])
    missing = [m for m in breakdown.get("missing_keywords", []) if ats._is_actionable_skill(m)]
    verified_low = {v.lower() for v in (verified_terms or [])}
    addable = [m for m in missing if m.lower() in verified_low]
    omitted = [m for m in missing if m.lower() not in verified_low]

    issues: list[str] = []
    if structure.get("uses_objective"):
        issues.append("Uses a generic objective instead of a role-focused professional summary.")
    if not structure.get("summary_present"):
        issues.append("No professional summary present.")

    return ResumeIntel(
        bullet_coaching=coaching,
        summary_review={"present": bool(structure.get("summary_present")), "issues": issues, "suggestion": None},
        skills_alignment={"strong": matched, "weak": [], "missing": addable, "omitted_for_truth": omitted},
        powered=False,
    )


def _parse(raw: str, *, fallback: ResumeIntel) -> ResumeIntel:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        return fallback
    coaching = [
        {"original": str(c.get("original", "")), "framework": str(c.get("framework", "")),
         "suggestion": str(c.get("suggestion", ""))}
        for c in (data.get("bullet_coaching") or []) if isinstance(c, dict) and c.get("suggestion")
    ]
    sr = data.get("summary_review") or {}
    summary_review = {
        "present": bool(sr.get("present", fallback.summary_review.get("present", False))),
        "issues": [str(i) for i in (sr.get("issues") or [])],
        "suggestion": (str(sr["suggestion"]) if sr.get("suggestion") else None),
    }
    sa = data.get("skills_alignment") or {}
    skills_alignment = {
        "strong": [str(x) for x in (sa.get("strong") or [])],
        "weak": [str(x) for x in (sa.get("weak") or [])],
        "missing": [str(x) for x in (sa.get("missing") or [])],
        "omitted_for_truth": [str(x) for x in (sa.get("omitted_for_truth") or fallback.skills_alignment.get("omitted_for_truth", []))],
    }
    return ResumeIntel(
        bullet_coaching=coaching or fallback.bullet_coaching,
        summary_review=summary_review,
        skills_alignment=skills_alignment,
        powered=True,
    )


async def analyze(
    *, cv_json: dict, cv_text: str, jd_text: str, role_title: str,
    breakdown: dict, structure: dict, verified_terms: list[str] | None = None,
) -> ResumeIntel:
    from app.llm import client

    offline = _offline(cv_json=cv_json, breakdown=breakdown, structure=structure, verified_terms=verified_terms)
    if not client.is_live("resume_intel"):
        return offline

    system = (
        "You are a resume coach. Return improvement SUGGESTIONS that a human will verify — "
        "never rewrite the CV yourself. STRICT: use ONLY facts present in the provided CV and "
        "verified-terms list; never invent metrics, tools, employers, or achievements. For each "
        "weak or vague bullet, propose a PAR (Problem-Action-Result) or XYZ (accomplished X, "
        "measured by Y, doing Z) reframe that keeps every fact truthful; if no real outcome "
        "exists, suggest a stronger verb only. Assess the professional summary (must be a "
        "recruiter-focused summary, not a generic objective). Return JSON ONLY: {bullet_coaching:"
        "[{original, framework, suggestion}], summary_review:{present, issues:[], suggestion}, "
        "skills_alignment:{strong:[], weak:[], missing:[], omitted_for_truth:[]}}."
    )
    prompt = json.dumps({
        "role_title": role_title,
        "job_description": jd_text,
        "cv_text": (cv_text or "")[:12000],
        "verified_terms": verified_terms or [],
        "rule_based_matched": breakdown.get("matched_keywords", []),
        "rule_based_missing": breakdown.get("missing_keywords", []),
    }, indent=2)

    raw = await client.try_complete_text(system, prompt, max_tokens=1500, feature="resume_intel")
    if raw is None:
        return offline
    try:
        return _parse(raw, fallback=offline)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return offline


def analysis_to_dict(a: ResumeIntel) -> dict:
    return {
        "bullet_coaching": a.bullet_coaching,
        "summary_review": a.summary_review,
        "skills_alignment": a.skills_alignment,
        "ai_powered": a.powered,
    }

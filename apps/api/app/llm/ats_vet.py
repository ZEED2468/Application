"""AI-assisted vetting of rule-based ATS gap prompts.

Rule-based scoring runs first; this module reviews candidate gaps against the
full profile + JD and returns only actionable confirm-true prompts. The model
must not invent skills that are absent from the JD or already evidenced in the
profile.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.pipelines.apply import ats


@dataclass(slots=True)
class VettedGap:
    skill: str
    question: str
    reason: str


@dataclass(slots=True)
class VetResult:
    gaps: list[VettedGap]
    removed: list[str]
    notes: str | None = None


def _profile_text(profile: dict) -> str:
    parts: list[str] = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(profile)
    return " ".join(parts).lower()


def _allowed_skill(skill: str, *, jd_text: str, candidate_gaps: list[str], missing_keywords: list[str]) -> bool:
    skill_l = skill.strip().lower()
    if not skill_l or not ats._is_actionable_skill(skill_l):
        return False
    pools = {g.lower() for g in candidate_gaps} | {m.lower() for m in missing_keywords}
    if skill_l in pools:
        return True
    norm = ats._normalize_token(skill_l)
    if norm in {ats._normalize_token(p) for p in pools}:
        return True
    return skill_l in (jd_text or "").lower()


def _default_question(skill: str, reason: str) -> str:
    detail = f" {reason}" if reason else ""
    return (
        f'The JD calls for "{skill}" but it is not clearly reflected in the profile.'
        f"{detail} Does the hunter have genuine {skill} experience?"
    )


def _parse_vet_response(
    raw: str,
    *,
    jd_text: str,
    candidate_gaps: list[str],
    missing_keywords: list[str],
    profile: dict,
    limit: int,
) -> VetResult:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    profile_blob = _profile_text(profile)
    cv_tokens = ats._cv_tokens(profile_blob)

    gaps: list[VettedGap] = []
    for item in data.get("gaps") or []:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip()
        if not skill or not _allowed_skill(
            skill, jd_text=jd_text, candidate_gaps=candidate_gaps, missing_keywords=missing_keywords
        ):
            continue
        if ats._keyword_matches(skill, profile_blob, cv_tokens):
            continue
        reason = str(item.get("reason") or "").strip()
        question = str(item.get("question") or "").strip() or _default_question(skill, reason)
        if skill.lower() not in question.lower():
            question = _default_question(skill, reason)
        gaps.append(VettedGap(skill=skill, question=question, reason=reason))
        if len(gaps) >= limit:
            break

    removed = [
        str(x).strip()
        for x in (data.get("removed") or [])
        if str(x).strip()
    ]
    notes = str(data.get("notes") or "").strip() or None
    return VetResult(gaps=gaps, removed=removed, notes=notes)


def vet_gaps_offline(
    *,
    profile: dict,
    jd_text: str,
    candidate_gaps: list[str],
    missing_keywords: list[str],
    limit: int = 5,
) -> VetResult:
    """Deterministic fallback: keep actionable gaps the profile does not evidence."""
    profile_blob = _profile_text(profile)
    cv_tokens = ats._cv_tokens(profile_blob)
    gaps: list[VettedGap] = []
    removed: list[str] = []

    for skill in candidate_gaps:
        if not _allowed_skill(
            skill, jd_text=jd_text, candidate_gaps=candidate_gaps, missing_keywords=missing_keywords
        ):
            removed.append(skill)
            continue
        if ats._keyword_matches(skill, profile_blob, cv_tokens):
            removed.append(skill)
            continue
        gaps.append(
            VettedGap(
                skill=skill,
                question=_default_question(skill, "Rule-based match flagged this as missing."),
                reason="Not found in the profile text.",
            )
        )
        if len(gaps) >= limit:
            break

    for skill in missing_keywords:
        if skill in candidate_gaps or skill in removed:
            continue
        if not ats._is_actionable_skill(skill):
            removed.append(skill)

    return VetResult(
        gaps=gaps,
        removed=removed,
        notes="Offline vet applied (configure an LLM for full AI review).",
    )


async def vet_gaps(
    *,
    profile: dict,
    jd_text: str,
    role_title: str,
    candidate_gaps: list[str],
    missing_keywords: list[str],
    matched_keywords: list[str] | None = None,
    limit: int = 5,
) -> VetResult:
    from app.llm import client

    if not client.is_live("ats_vet"):
        return vet_gaps_offline(
            profile=profile,
            jd_text=jd_text,
            candidate_gaps=candidate_gaps,
            missing_keywords=missing_keywords,
            limit=limit,
        )

    system = (
        "You review ATS gap suggestions for a job application assistant. "
        "Given a job description, a hunter profile, and rule-based candidate gaps, "
        "return JSON ONLY with keys: gaps (array of {skill, question, reason}), "
        "removed (array of strings), notes (string). "
        "Include ONLY genuine technical or role requirements worth confirming. "
        "Drop generic English (good, understanding, environment, skills). "
        "Do NOT suggest skills already evidenced in the profile (e.g. JavaScript does "
        "not mean Java is covered). Do NOT invent skills absent from the JD. "
        "Each question must quote the skill in double quotes."
    )
    prompt = json.dumps(
        {
            "role_title": role_title,
            "job_description": jd_text,
            "profile": profile,
            "rule_based_candidate_gaps": candidate_gaps,
            "rule_based_missing_keywords": missing_keywords,
            "rule_based_matched_keywords": matched_keywords or [],
            "max_gaps": limit,
        },
        indent=2,
    )
    raw = await client.complete_text(system, prompt, max_tokens=1200, feature="ats_vet")
    try:
        return _parse_vet_response(
            raw,
            jd_text=jd_text,
            candidate_gaps=candidate_gaps,
            missing_keywords=missing_keywords,
            profile=profile,
            limit=limit,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return vet_gaps_offline(
            profile=profile,
            jd_text=jd_text,
            candidate_gaps=candidate_gaps,
            missing_keywords=missing_keywords,
            limit=limit,
        )

"""Extract structured profile fields from raw CV text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.pipelines.apply.cv_parse import naive_skills


@dataclass(slots=True)
class StructuredProfile:
    headline: str | None
    summary: str | None
    skills: list[str]
    experience: list[dict]
    projects: list[dict]
    education: list[dict]
    structured_by: str  # "llm" | "offline"


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _leaf_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [s for v in value.values() for s in _leaf_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _leaf_strings(v)]
    return []


def _truth_bounded(source: str, structured: dict) -> bool:
    """Every extracted string must appear in the source CV text."""
    norm_source = _normalize(source)
    for s in _leaf_strings(structured):
        if _normalize(s) not in norm_source:
            return False
    return True


def structure_offline(text: str, *, track: str | None = None) -> StructuredProfile:
    body = (text or "").strip()
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    headline = lines[0][:200] if lines else None
    summary = " ".join(lines[:6])[:1200] if lines else None
    skills = naive_skills(body)
    experience = [{"bullets": lines[:80]}] if lines else []
    return StructuredProfile(
        headline=headline,
        summary=summary,
        skills=skills,
        experience=experience,
        projects=[],
        education=[],
        structured_by="offline",
    )


def _parse_llm_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


async def structure_cv(text: str, *, track: str | None = None) -> StructuredProfile:
    """Parse CV text into profile fields. LLM when configured, else offline."""
    from app.llm import client

    body = (text or "").strip()
    if len(body) < 40:
        return structure_offline(body, track=track)

    if not client.is_live("cv_structure"):
        return structure_offline(body, track=track)

    system = (
        "Extract a CV into JSON ONLY. Keys: headline, summary, skills (string array), "
        "experience (array of {title, company, bullets: string[]}), "
        "projects (array of {name, description}), "
        "education (array of {school, details}). "
        "STRICT: copy facts verbatim from the CV — do not invent employers, dates, or skills. "
        "Bullets must be exact phrases or sentences from the source text."
    )
    prompt = f"TRACK LENS: {track or 'general'}\n\nCV TEXT:\n{body[:14000]}"
    raw = await client.try_complete_text(system, prompt, max_tokens=2500, feature="cv_structure")
    if raw is None:
        return structure_offline(body, track=track)
    try:
        data = _parse_llm_json(raw)
        structured = {
            "headline": data.get("headline"),
            "summary": data.get("summary"),
            "skills": data.get("skills") or [],
            "experience": data.get("experience") or [],
            "projects": data.get("projects") or [],
            "education": data.get("education") or [],
        }
        if _truth_bounded(body, structured):
            return StructuredProfile(
                headline=str(structured["headline"]).strip() if structured["headline"] else None,
                summary=str(structured["summary"]).strip() if structured["summary"] else None,
                skills=[str(s).strip() for s in structured["skills"] if str(s).strip()],
                experience=[e for e in structured["experience"] if isinstance(e, dict)],
                projects=[p for p in structured["projects"] if isinstance(p, dict)],
                education=[e for e in structured["education"] if isinstance(e, dict)],
                structured_by="llm",
            )
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return structure_offline(body, track=track)


def apply_to_profile(profile, structured: StructuredProfile) -> None:
    if structured.headline:
        profile.headline = structured.headline
    if structured.summary:
        profile.summary = structured.summary
    if structured.skills:
        profile.skills = structured.skills
    if structured.experience:
        profile.experience = structured.experience
    if structured.projects:
        profile.projects = structured.projects
    if structured.education:
        profile.education = structured.education

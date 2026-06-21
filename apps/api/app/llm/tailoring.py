"""Tailoring engine: master profile -> track lens -> JD tailoring.

Strict truth boundary (PRD §5.1.5, §10): only reorder/reframe facts already in
the master profile; never fabricate. The deterministic (fake) path does pure
selection + reordering, which is *provably* truth-bounded — `assert_truth_bounded`
verifies every emitted fact traces back to the profile. The live path constrains
the model to the profile as its only source and stores a diff for VA review.
"""

from __future__ import annotations

import json
import re

import structlog

log = structlog.get_logger(__name__)

_TOKEN = re.compile(r"[a-z0-9+#.]+")


def _parse_cv_json(text: str) -> dict:
    """Parse the model's tailoring output, tolerating ```json fences / surrounding
    prose. Raises if no JSON object can be recovered."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    if not s.startswith("{"):
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end > start:
            s = s[start : end + 1]
    data = json.loads(s)
    if not isinstance(data, dict):
        raise ValueError("tailoring did not return a JSON object")
    return data


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


def _flatten_skills(skills) -> list[str]:
    if isinstance(skills, dict):
        out: list[str] = []
        for v in skills.values():
            out.extend(v if isinstance(v, list) else [v])
        return [str(s) for s in out]
    if isinstance(skills, list):
        return [str(s) for s in skills]
    return []


def _entry_text(entry: dict) -> str:
    parts = [str(entry.get(k, "")) for k in ("title", "role", "company", "name", "description")]
    parts.extend(str(b) for b in entry.get("bullets", []))
    return " ".join(parts)


def _rank(entries: list[dict], job_tokens: set[str]) -> list[tuple[int, dict]]:
    scored = [
        (len(_tokens(_entry_text(e)) & job_tokens), i, e) for i, e in enumerate(entries)
    ]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [(i, e) for _, i, e in scored]


def tailor_fake(profile: dict, *, job_title: str, job_description: str | None) -> tuple[dict, dict]:
    """Select + reorder the profile's own items by relevance to the job."""
    job_tokens = _tokens(f"{job_title} {job_description or ''}")

    skills = _flatten_skills(profile.get("skills"))
    emphasized = [s for s in skills if _tokens(s) & job_tokens]
    rest = [s for s in skills if s not in emphasized]

    experience = profile.get("experience") or []
    projects = profile.get("projects") or []
    ranked_exp = _rank(experience, job_tokens)
    ranked_proj = _rank(projects, job_tokens)

    cv_json = {
        "headline": profile.get("headline"),
        "summary": profile.get("summary"),
        "skills": emphasized + rest,
        "experience": [e for _, e in ranked_exp],
        "projects": [p for _, p in ranked_proj],
        "education": profile.get("education") or [],
        "links": profile.get("links") or {},
    }
    diff = {
        "skills_emphasized": emphasized,
        "experience_order": [i for i, _ in ranked_exp],
        "projects_order": [i for i, _ in ranked_proj],
        "strategy": "deterministic-selection",
    }
    return cv_json, diff


def _leaf_strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _leaf_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _leaf_strings(v)]
    return []


def assert_truth_bounded(profile: dict, cv_json: dict) -> None:
    """Guarantee every emitted string exists in the profile (no fabrication).

    Applies to the deterministic path; the live path relies on the constrained
    prompt + VA review instead, since reframing legitimately rewords text.
    """
    allowed = set(_leaf_strings(profile))
    for s in _leaf_strings(cv_json):
        if s not in allowed:
            raise ValueError(f"Tailoring fabricated a fact not in the profile: {s!r}")


async def tailor(
    profile: dict, *, job_title: str, job_description: str | None,
    priority_techs: list[str] | None = None,
) -> tuple[dict, dict]:
    """Public entry. Deterministic in fake mode; constrained LLM call otherwise.

    `priority_techs` are JD-critical technologies (strongly-recommended/must-have).
    In the live path the model is told to make those EXPLICIT in achievement format
    — but only when the profile already supports them (no fabrication).
    """
    from app.llm import client

    if not client.is_live("tailoring"):
        # Deterministic path can't reframe (it would invent text); it stays a pure,
        # provably truth-bounded selection/reorder. Record the requested priorities.
        cv_json, diff = tailor_fake(
            profile, job_title=job_title, job_description=job_description
        )
        assert_truth_bounded(profile, cv_json)
        diff["priority_techs"] = priority_techs or []
        return cv_json, diff

    system = (
        "You tailor a CV to a job. STRICT RULE: use ONLY facts present in the "
        "provided master profile (its skills, experience, projects, and summary/CV "
        "text). Reorder and reframe for relevance; never invent employers, dates, "
        "skills, achievements, or metrics.\n"
        "ACHIEVEMENT FORMAT: where the profile shows the candidate actually used a "
        "technology, state it EXPLICITLY in an experience bullet as 'Used <tech> to "
        "<do X>, achieving <Y>' so an ATS parses the skill in context. Draw <X>/<Y> "
        "only from real outcomes in the profile; if no outcome is stated, omit the "
        "achieving clause rather than invent one.\n"
        "Return JSON with keys: headline, summary, skills, experience, projects, "
        "education, links."
    )
    priority_line = ""
    if priority_techs:
        priority_line = (
            "JD-CRITICAL TECHNOLOGIES (make these explicit in achievement format ONLY "
            "if the profile genuinely supports them; never claim one it does not): "
            f"{', '.join(priority_techs)}\n\n"
        )
    prompt = (
        f"MASTER PROFILE (the only allowed facts):\n{json.dumps(profile)}\n\n"
        f"{priority_line}"
        f"JOB TITLE: {job_title}\nJOB DESCRIPTION: {job_description or ''}\n\n"
        "Return only the JSON object."
    )
    try:
        text = await client.complete_text(system, prompt, max_tokens=2500, feature="tailoring")
        cv_json = _parse_cv_json(text)
        diff = {"strategy": "llm", "model": True, "achievement_format": True,
                "priority_techs": priority_techs or []}
        return cv_json, diff
    except Exception as exc:
        # Live tailoring must never break generation (a bad/non-JSON model reply or
        # an API error). Fall back to the deterministic, provably truth-bounded path.
        log.warning("tailoring.live_failed", error=str(exc), exc_type=type(exc).__name__)
        cv_json, diff = tailor_fake(
            profile, job_title=job_title, job_description=job_description
        )
        assert_truth_bounded(profile, cv_json)
        diff["priority_techs"] = priority_techs or []
        diff["fell_back"] = "llm_failed"
        return cv_json, diff

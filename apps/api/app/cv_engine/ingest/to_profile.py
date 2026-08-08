"""Map a deterministic ParsedCv onto a MasterProfile (the upload structurer).

Extends what `cv_structure.apply_to_profile` did (headline/summary/skills/experience/
projects/education) with what the deterministic parser newly extracts: dated experience,
social links, and certifications/languages (into verified_extras, where the engine's
enrich step already promotes them to real sections). Only truthy fields overwrite — a
low-confidence parse never blanks existing data.
"""

from __future__ import annotations

from app.cv_engine.ingest.parse_cv import ParsedCv
from app.models.master_profile import MasterProfile


def apply_parsed_to_profile(profile: MasterProfile, parsed: ParsedCv) -> None:
    cv = parsed.cv_json or {}
    if cv.get("headline"):
        profile.headline = cv["headline"]
    if cv.get("summary"):
        profile.summary = cv["summary"]
    if cv.get("skills"):
        profile.skills = cv["skills"]
    if cv.get("experience"):
        profile.experience = cv["experience"]
    if cv.get("education"):
        profile.education = cv["education"]
    if cv.get("projects"):
        profile.projects = cv["projects"]

    # Only social links belong on profile.links (email/phone are contact, not portfolio).
    social = {k: v for k, v in (cv.get("links") or {}).items() if k in ("linkedin", "github")}
    if social:
        merged = dict(profile.links or {})
        merged.update(social)
        profile.links = merged

    extras = dict(profile.verified_extras or {})
    changed = False
    for cat in ("certifications", "languages"):
        if cv.get(cat):
            extras[cat] = list(dict.fromkeys([*(extras.get(cat) or []), *cv[cat]]))
            changed = True
    if changed:
        profile.verified_extras = extras

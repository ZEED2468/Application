"""Master-profile data access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Track
from app.models.master_profile import MasterProfile


async def get_by_user_track(
    session: AsyncSession, *, user_id: UUID, track: Track
) -> MasterProfile | None:
    stmt = select(MasterProfile).where(
        MasterProfile.user_id == user_id, MasterProfile.track == track
    )
    return (await session.execute(stmt)).scalar_one_or_none()


# Verified-extra categories promoted to their OWN CV sections by
# generation.enrich_from_verified_extras — so they must NOT also be folded into the
# flat skills list here (that would duplicate them). Keep the two in sync.
PROMOTED_EXTRA_CATEGORIES = frozenset(
    {"certifications", "languages", "open_source", "side_projects"}
)


def _extra_terms(profile: MasterProfile) -> list[str]:
    """Flatten the *skill-like* verified extras + preferred skills into terms that
    become part of the allowed truth corpus (user-asserted-true facts). Promoted
    categories (certifications/languages/projects) are rendered as their own sections
    instead, so they're skipped here."""
    terms: list[str] = []
    for cat, v in (getattr(profile, "verified_extras", None) or {}).items():
        if cat in PROMOTED_EXTRA_CATEGORIES:
            continue
        if isinstance(v, list):
            terms.extend(str(x) for x in v if str(x).strip())
        elif isinstance(v, str) and v.strip():
            terms.append(v.strip())
    terms.extend(str(s) for s in (getattr(profile, "preferred_skills", None) or []) if str(s).strip())
    return list(dict.fromkeys(terms))


def _augment_skills(skills, extra: list[str]):
    if not extra:
        return skills
    if isinstance(skills, dict):
        out = dict(skills)
        existing = out.get("verified") or []
        out["verified"] = list(dict.fromkeys([*existing, *extra]))
        return out
    base = list(skills) if isinstance(skills, list) else []
    for e in extra:
        if e not in base:
            base.append(e)
    return base


def profile_to_dict(profile: MasterProfile) -> dict:
    experience = profile.experience or []
    summary = profile.summary
    # Upload path stores raw CV text in truth_corpus; use it when structured fields are empty.
    if profile.truth_corpus:
        if not summary:
            summary = profile.truth_corpus[:4000]
        if not experience:
            lines = [ln.strip() for ln in profile.truth_corpus.splitlines() if ln.strip()]
            if lines:
                experience = [{"bullets": lines[:80]}]

    extra = _extra_terms(profile)
    return {
        "headline": profile.headline,
        "summary": summary,
        # Verified extras + preferred skills join the allowed skill set so tailoring can
        # surface them — they are user-asserted-true, so this stays truth-bounded.
        "skills": _augment_skills(profile.skills, extra),
        "experience": experience,
        "education": profile.education,
        "projects": profile.projects,
        "links": profile.links,
        "verified_extras": getattr(profile, "verified_extras", None) or {},
        "preferred_skills": [str(s) for s in (getattr(profile, "preferred_skills", None) or [])],
    }

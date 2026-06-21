"""Load per-track CV previews for track classification."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Track
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.core.enums import ParseStatus


def _skills_preview(skills) -> str:
    if isinstance(skills, list):
        return " ".join(str(s) for s in skills)
    if isinstance(skills, dict):
        parts: list[str] = []
        for v in skills.values():
            if isinstance(v, list):
                parts.extend(str(x) for x in v)
            else:
                parts.append(str(v))
        return " ".join(parts)
    return ""


def _profile_preview(profile: MasterProfile) -> str:
    parts = [
        profile.headline or "",
        profile.summary or "",
        _skills_preview(profile.skills),
        profile.truth_corpus or "",
    ]
    return " ".join(p for p in parts if p).strip()


async def available_track_previews(
    session: AsyncSession, *, user_id: UUID,
) -> dict[Track, str]:
    """Tracks with a parsed source CV -> text preview for matching."""
    role_cvs = {
        rc.track: rc
        for rc in (await session.execute(
            select(RoleCv).where(RoleCv.user_id == user_id)
        )).scalars().all()
    }
    profiles = {
        p.track: p
        for p in (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user_id)
        )).scalars().all()
    }
    out: dict[Track, str] = {}
    for track in Track:
        rc = role_cvs.get(track)
        if rc is None or rc.parse_status is not ParseStatus.parsed:
            continue
        profile = profiles.get(track)
        preview = _profile_preview(profile) if profile else ""
        if preview:
            out[track] = preview[:4000]
    return out

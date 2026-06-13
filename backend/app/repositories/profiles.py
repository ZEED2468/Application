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


def profile_to_dict(profile: MasterProfile) -> dict:
    return {
        "headline": profile.headline,
        "summary": profile.summary,
        "skills": profile.skills,
        "experience": profile.experience,
        "education": profile.education,
        "projects": profile.projects,
        "links": profile.links,
    }

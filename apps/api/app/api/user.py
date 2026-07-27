"""User readiness API — the single source of truth for onboarding / setup progress.

Aggregates the setup milestones (AI provider, track, resume, profile, cover template)
into a progress % + a `next_action`, plus per-track readiness. The dashboard, the
onboarding checklist, and smart reminders all read from here.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tracks import _label, _readiness, _rows_by_slug
from app.core.enums import LatexKind
from app.db import get_session
from app.deps import current_user
from app.models.cover_letter import CoverLetterTemplate
from app.models.latex_template import LatexTemplate
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.models.user_llm_credential import UserLlmCredential

router = APIRouter(prefix="/user", tags=["user"])
log = structlog.get_logger(__name__)


def _step(step_id: str, label: str, completed: bool, route: str, action_label: str) -> dict:
    return {
        "id": step_id, "label": label, "completed": completed,
        "action": {"label": action_label, "route": route},
    }


@router.get("/readiness")
async def readiness(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    creds = (await session.execute(
        select(UserLlmCredential).where(UserLlmCredential.user_id == user.id)
    )).scalars().all()
    has_key = any(c.encrypted_api_key for c in creds)
    key_valid = any(c.encrypted_api_key and c.status == "configured" for c in creds)

    profiles = (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalars().all()
    role_cvs = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id)
    )).scalars().all()
    cover_tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()
    latex_cover = (await session.execute(
        select(LatexTemplate).where(
            LatexTemplate.user_id == user.id, LatexTemplate.kind == LatexKind.cover
        )
    )).scalars().all()
    has_cover = bool((cover_tpl and cover_tpl.body) or any(lt.source for lt in latex_cover))

    steps = [
        _step("ai_provider", "Configure an AI provider", has_key, "/settings", "Open AI Settings"),
        _step("track_created", "Create your first track", bool(profiles), "/profile", "Create Track"),
        _step("resume_uploaded", "Upload a resume", bool(role_cvs), "/profile", "Upload Resume"),
        _step("profile_confirmed", "Confirm your profile",
              any(p.confirmed for p in profiles), "/profile", "Review Profile"),
        _step("cover_letter_template", "Add a cover-letter template",
              has_cover, "/profile", "Add Template"),
    ]
    done = sum(1 for s in steps if s["completed"])
    progress = round(100 * done / len(steps)) if steps else 0
    next_action = next((s for s in steps if not s["completed"]), None)

    # Per-track readiness (reuses the tracks logic; read-only, no row backfill here).
    rows = await _rows_by_slug(session, user.id)
    ready = await _readiness(session, user.id)
    tracks = []
    for slug in sorted(set(rows) | set(ready)):
        r = ready.get(slug, {"resume": False, "cover_letter": False, "confirmed": False})
        row = rows.get(slug)
        status = (
            "archived" if (row and row.archived_at)
            else ("ready" if r["resume"] else "setup_required")
        )
        tracks.append({
            "id": str(row.id) if row else None, "slug": slug,
            "name": row.name if row else _label(slug), "status": status,
            "resume": r["resume"], "cover_letter": r["cover_letter"],
        })

    return {
        "progress": progress,
        "complete": next_action is None,
        "steps": steps,
        "next_action": next_action,
        "api_key_validated": key_valid,
        "tracks": tracks,
    }

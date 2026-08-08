"""Tracks API — first-class career tracks with readiness + lifecycle.

Business rule: a track is *incomplete* until it has a resume (CV). This layer sits on
top of the existing per-(user, track) data by slug: readiness (ready vs setup_required)
is derived from whether a RoleCv exists for the slug; `archived_at` on the Track row is
the only stored lifecycle state. `require_track_resume` is the guard AI endpoints use.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LatexKind, ParseStatus
from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import current_user
from app.models.cover_letter import CoverLetterTemplate
from app.models.latex_template import LatexTemplate
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.track_entity import Track as TrackRow
from app.models.user import User

router = APIRouter(prefix="/tracks", tags=["tracks"])
log = structlog.get_logger(__name__)

_BUILTIN = {"frontend": "Frontend", "backend": "Backend", "general": "General"}


def _tv(obj) -> str:
    """Slug value of a row whose `track` column may be an enum or a raw string."""
    t = obj.track
    return t.value if hasattr(t, "value") else str(t)


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "track"


def _label(slug: str) -> str:
    return _BUILTIN.get(slug) or slug.replace("-", " ").title()


class TrackOut(BaseModel):
    id: str
    slug: str
    name: str
    status: str  # setup_required | ready | archived
    resume: bool
    cover_letter: bool
    confirmed: bool
    target_roles: list[str] = []


class CreateTrackBody(BaseModel):
    name: str
    slug: str | None = None


class RenameTrackBody(BaseModel):
    name: str


async def _readiness(session: AsyncSession, user_id) -> dict[str, dict]:
    """slug -> {resume, cover_letter, confirmed, target_roles} from existing per-track data."""
    role_cvs = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user_id)
    )).scalars().all()
    profiles = (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user_id)
    )).scalars().all()
    latex = (await session.execute(
        select(LatexTemplate).where(LatexTemplate.user_id == user_id)
    )).scalars().all()
    cover_tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user_id)
    )).scalar_one_or_none()

    ready: dict[str, dict] = {}

    def slot(slug: str) -> dict:
        return ready.setdefault(
            slug, {"resume": False, "cover_letter": False, "confirmed": False, "target_roles": []}
        )

    for rc in role_cvs:
        slot(_tv(rc))["resume"] = True
    for p in profiles:
        s = slot(_tv(p))
        s["confirmed"] = bool(p.confirmed)
        s["target_roles"] = list(p.target_roles or [])
    for lt in latex:
        if lt.kind is LatexKind.cover and lt.source:
            slot(_tv(lt))["cover_letter"] = True
    # A per-user plaintext cover template counts as cover coverage for every track.
    if cover_tpl and cover_tpl.body:
        for s in ready.values():
            s["cover_letter"] = True
    return ready


def _status(row: TrackRow, r: dict) -> str:
    if row.archived_at:
        return "archived"
    return "ready" if r.get("resume") else "setup_required"


async def _rows_by_slug(session, user_id) -> dict[str, TrackRow]:
    return {
        t.slug: t for t in (await session.execute(
            select(TrackRow).where(TrackRow.user_id == user_id)
        )).scalars().all()
    }


@router.get("", response_model=list[TrackOut])
async def list_tracks(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> list[TrackOut]:
    """Every track the user has (persisted rows + any track with existing data),
    with derived readiness. Backfills a Track row for data-only slugs so each has an id."""
    rows = await _rows_by_slug(session, user.id)
    ready = await _readiness(session, user.id)
    # Lazily persist a Track row for slugs that have data but no row yet.
    for slug in ready:
        if slug not in rows:
            row = TrackRow(user_id=user.id, slug=slug, name=_label(slug))
            session.add(row)
            rows[slug] = row
    await session.flush()

    out: list[TrackOut] = []
    for slug in sorted(set(rows) | set(ready)):
        row = rows[slug]
        r = ready.get(slug, {"resume": False, "cover_letter": False, "confirmed": False, "target_roles": []})
        out.append(TrackOut(
            id=str(row.id), slug=slug, name=row.name, status=_status(row, r),
            resume=r["resume"], cover_letter=r["cover_letter"], confirmed=r["confirmed"],
            target_roles=r["target_roles"],
        ))
    return out


@router.post("", response_model=TrackOut)
async def create_track(
    body: CreateTrackBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> TrackOut:
    name = (body.name or "").strip()
    if not name:
        raise DomainError("A track name is required.")
    slug = _slugify(body.slug or name)
    rows = await _rows_by_slug(session, user.id)
    if slug in rows and rows[slug].archived_at is None:
        raise DomainError(f"A track '{slug}' already exists.", code="track_exists")
    row = rows.get(slug)
    if row is None:
        row = TrackRow(user_id=user.id, slug=slug, name=name)
        session.add(row)
    else:  # un-archive + rename an archived slug
        row.name = name
        row.archived_at = None
    await session.flush()
    ready = (await _readiness(session, user.id)).get(slug, {})
    return TrackOut(
        id=str(row.id), slug=slug, name=row.name, status=_status(row, ready),
        resume=bool(ready.get("resume")), cover_letter=bool(ready.get("cover_letter")),
        confirmed=bool(ready.get("confirmed")), target_roles=list(ready.get("target_roles") or []),
    )


async def _get_row(session, user_id, track_id: UUID) -> TrackRow:
    row = await session.get(TrackRow, track_id)
    if row is None or row.user_id != user_id:
        raise NotFoundError("Track not found")
    return row


@router.patch("/{track_id}", response_model=TrackOut)
async def rename_track(
    track_id: UUID, body: RenameTrackBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> TrackOut:
    row = await _get_row(session, user.id, track_id)
    name = (body.name or "").strip()
    if not name:
        raise DomainError("A track name is required.")
    row.name = name
    await session.flush()
    ready = (await _readiness(session, user.id)).get(row.slug, {})
    return TrackOut(
        id=str(row.id), slug=row.slug, name=row.name, status=_status(row, ready),
        resume=bool(ready.get("resume")), cover_letter=bool(ready.get("cover_letter")),
        confirmed=bool(ready.get("confirmed")), target_roles=list(ready.get("target_roles") or []),
    )


@router.post("/{track_id}/archive", response_model=TrackOut)
async def archive_track(
    track_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> TrackOut:
    row = await _get_row(session, user.id, track_id)
    row.archived_at = datetime.now(timezone.utc)
    await session.flush()
    return TrackOut(id=str(row.id), slug=row.slug, name=row.name, status="archived",
                    resume=False, cover_letter=False, confirmed=False, target_roles=[])


@router.post("/{track_id}/unarchive", response_model=TrackOut)
async def unarchive_track(
    track_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> TrackOut:
    row = await _get_row(session, user.id, track_id)
    row.archived_at = None
    await session.flush()
    ready = (await _readiness(session, user.id)).get(row.slug, {})
    return TrackOut(
        id=str(row.id), slug=row.slug, name=row.name, status=_status(row, ready),
        resume=bool(ready.get("resume")), cover_letter=bool(ready.get("cover_letter")),
        confirmed=bool(ready.get("confirmed")), target_roles=list(ready.get("target_roles") or []),
    )


@router.post("/{track_id}/resume/from/{source_track_id}", response_model=TrackOut)
async def duplicate_resume(
    track_id: UUID, source_track_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> TrackOut:
    """Assign an existing track's resume to this track (duplicate + edit independently)."""
    target = await _get_row(session, user.id, track_id)
    source = await _get_row(session, user.id, source_track_id)
    src_cv = next((rc for rc in (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id)
    )).scalars().all() if _tv(rc) == source.slug), None)
    if src_cv is None:
        raise DomainError("The source track has no resume to copy.", code="source_resume_missing")
    src_profile = next((p for p in (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalars().all() if _tv(p) == source.slug), None)

    tgt_cv = next((rc for rc in (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id)
    )).scalars().all() if _tv(rc) == target.slug), None)
    if tgt_cv is None:
        tgt_cv = RoleCv(user_id=user.id, track=target.slug)
        session.add(tgt_cv)
    tgt_cv.original_filename = src_cv.original_filename
    tgt_cv.source_file_key = src_cv.source_file_key  # same stored object; edited copy diverges later
    tgt_cv.parse_status = src_cv.parse_status

    if src_profile is not None:
        tgt_profile = next((p for p in (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalars().all() if _tv(p) == target.slug), None)
        if tgt_profile is None:
            tgt_profile = MasterProfile(user_id=user.id, track=target.slug)
            session.add(tgt_profile)
        for f in ("headline", "summary", "skills", "experience", "education", "projects",
                  "links", "truth_corpus", "verified_extras", "preferred_skills"):
            setattr(tgt_profile, f, getattr(src_profile, f))
        tgt_profile.confirmed = False  # re-confirm the copy
    await session.flush()
    ready = (await _readiness(session, user.id)).get(target.slug, {})
    return TrackOut(
        id=str(target.id), slug=target.slug, name=target.name, status=_status(target, ready),
        resume=bool(ready.get("resume")), cover_letter=bool(ready.get("cover_letter")),
        confirmed=bool(ready.get("confirmed")), target_roles=list(ready.get("target_roles") or []),
    )


async def track_generation_readiness(session: AsyncSession, user_id, track) -> dict:
    """Non-raising: can we generate a *real* CV for this track? Ready requires a source CV
    that actually PARSED plus a profile with real content (non-empty truth_corpus) — so we
    never tailor from an empty placeholder and pass off a name-only document. Returns a
    structured dict the job detail exposes and the gate raises from."""
    slug = track.value if hasattr(track, "value") else str(track or "")
    label = _BUILTIN.get(slug, slug.title() if slug else "this")
    role_cvs = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user_id)
    )).scalars().all()
    role_cv = next((rc for rc in role_cvs if _tv(rc) == slug), None)
    profiles = (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user_id)
    )).scalars().all()
    prof = next((p for p in profiles if _tv(p) == slug), None)

    def blocked(reason: str, title: str, message: str) -> dict:
        return {
            "ready": False, "reason": reason, "title": title, "message": message,
            "remediation": message,
            "action": {"label": "Upload CV", "route": f"/profile?track={slug}"},
        }

    if role_cv is None:
        return blocked(
            "no_cv", f"{label} CV needed",
            f"No CV for the {label} track yet — upload one so the résumé is tailored from "
            f"your real experience, not a blank template. Or change the track on the right.",
        )
    if role_cv.parse_status is not ParseStatus.parsed:
        return blocked(
            "cv_unparsed", f"{label} CV couldn't be read",
            f"We couldn't read your {label} CV (the upload didn't parse), so there's no "
            f"content to tailor from. Re-upload it on your Profile.",
        )
    has_content = prof is not None and bool(
        (prof.truth_corpus and prof.truth_corpus.strip()) or prof.skills or prof.experience
    )
    if not has_content:
        return blocked(
            "no_content", f"{label} profile is empty",
            f"Your {label} profile has no readable content yet. Re-upload your CV so the "
            f"résumé has real facts to work from.",
        )
    return {
        "ready": True, "reason": None, "title": None, "message": None,
        "remediation": None, "action": None,
    }


async def assert_track_generatable(session: AsyncSession, user_id, track) -> None:
    """Raise a structured, actionable DomainError when a track can't back a real CV."""
    r = await track_generation_readiness(session, user_id, track)
    if not r["ready"]:
        raise DomainError(
            r["message"], code="track_not_ready", title=r["title"],
            remediation=r["remediation"], action=r["action"],
        )


async def require_track_resume(session: AsyncSession, user_id, track) -> None:
    """Guard used by AI endpoints: raise a structured, actionable error unless the track has
    a source CV that actually PARSED (existence alone isn't enough — a failed upload would
    otherwise pass and generate from nothing)."""
    slug = track.value if hasattr(track, "value") else str(track or "")
    role_cvs = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user_id)
    )).scalars().all()
    matched = next((rc for rc in role_cvs if _tv(rc) == slug), None)
    if matched is None or matched.parse_status is not ParseStatus.parsed:
        raise DomainError(
            "This track does not have a readable resume yet. Upload (or re-upload) a "
            "resume for this track before using AI-powered features.",
            code="track_resume_required",
            remediation="Upload or re-upload a resume for this track.",
            action={"label": "Upload Resume", "route": f"/profile?track={slug}"},
        )

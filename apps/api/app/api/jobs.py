"""Jobs API — hunter-scoped list/detail, track override, generate CV, VA submit."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import ApplicationStatus, JobStatus, Origin, PrincipalType, Track, TrackerStatus
from app.core.errors import ConflictError, NotFoundError
from app.db import get_session
from app.deps import (
    Principal,
    authorize_owner,
    current_principal,
    current_user,
    scoped_user_ids,
)
from app.models.application import Application
from app.models.cover_letter import CoverLetter
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.outreach import Outreach
from app.models.reply import Reply
from app.models.thread import Thread
from app.models.user import User
from app.pipelines.apply import service
from app.repositories import applications as app_repo
from app.repositories import jobs as jobs_repo
from app.repositories import profiles as profiles_repo
from app.schemas.jobs import (
    GenerateResponse,
    SubmitResponse,
    TrackOverrideRequest,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class ApplicationStatusUpdate(BaseModel):
    status: TrackerStatus


def _actor(principal: Principal) -> str:
    kind = "va" if principal.type is PrincipalType.va else "hunter"
    return f"{kind}:{principal.id}"


def _gdocs_viewer_url(pdf_url: str | None) -> str | None:
    if not pdf_url:
        return None
    return f"https://docs.google.com/viewer?url={quote(pdf_url, safe='')}"


def _jd_preview(text: str | None, *, max_len: int = 100) -> str | None:
    if not text or not text.strip():
        return None
    t = text.strip()
    if len(t) <= max_len:
        return t
    return f"{t[:max_len].rstrip()}…"


async def _cv_for(session, job_id):
    return (await session.execute(
        select(GeneratedCv).where(GeneratedCv.job_id == job_id)
    )).scalar_one_or_none()


async def _cover_for(session, job_id):
    return (await session.execute(
        select(CoverLetter).where(CoverLetter.job_id == job_id)
    )).scalar_one_or_none()


async def _application_for(session, job_id):
    return (await session.execute(
        select(Application).where(Application.job_id == job_id)
    )).scalar_one_or_none()


async def _job_row(session, job: Job, *, hunter_name: str | None = None) -> dict:
    cv = await _cv_for(session, job.id)
    cover = await _cover_for(session, job.id)
    app = await _application_for(session, job.id)
    application_status = (
        app.tracker_status.value
        if app is not None
        else TrackerStatus.not_applied.value
    )
    description = job.description
    return {
        "id": str(job.id), "company": job.company, "title": job.title,
        "role": job.role_title or job.title,
        "role_title": job.role_title, "location": job.location, "url": job.url,
        "track": (job.track.value if job.track else None),
        "track_override": (job.track_override.value if job.track_override else None),
        "origin": job.origin.value, "status": job.status.value,
        "relevance_score": job.relevance_score,
        "ats_score": cv.ats_score if cv else None,
        "application_id": str(app.id) if app else None,
        "application_status": application_status,
        "tracker_status": application_status,
        "description": description,
        "jd_preview": _jd_preview(description),
        "resume_doc_url": _gdocs_viewer_url(cv.pdf_url if cv else None),
        "cover_letter_doc_url": _gdocs_viewer_url(cover.pdf_url if cover else None),
        "hunter_name": hunter_name,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.post("/discover")
async def discover(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Run job discovery NOW for the hunter's profiles (no 30-min beat wait) and
    return a per-source report. Newly-found jobs appear in the list immediately."""
    profiles = (
        await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )
    ).scalars().all()
    agg: dict[str, dict] = {}
    total = 0
    for profile in profiles:
        new_jobs, report = await service._run_sources(
            session, user_id=user.id, profile=profile
        )
        total += len(new_jobs)
        for r in report:
            a = agg.setdefault(
                r["source"], {"source": r["source"], "found": 0, "inserted": 0, "error": None}
            )
            a["found"] += r["found"]
            a["inserted"] += r["inserted"]
            if r["error"] and not a["error"]:
                a["error"] = r["error"]
    return {
        "discovered": total,
        "fake_mode": settings.use_fake_integrations,
        "profiles": len(profiles),
        "sources": list(agg.values()),
    }


@router.get("")
async def list_jobs(
    status: TrackerStatus | None = Query(
        default=None, description="Application tracker status filter"
    ),
    track: Track | None = Query(default=None),
    origin: Origin | None = Query(default=None),
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    # A hunter sees their own jobs; a VA sees jobs across every assigned hunter.
    user_ids = await scoped_user_ids(session, principal)
    is_va = principal.type is PrincipalType.va
    names = (
        {uid: (await session.get(User, uid)).name for uid in user_ids} if is_va else {}
    )
    rows: list[dict] = []
    for uid in user_ids:
        for j in await jobs_repo.list_for_user(session, user_id=uid):
            if track is not None and j.track != track:
                continue
            if origin is not None and j.origin != origin:
                continue
            row = await _job_row(session, j, hunter_name=names.get(uid))
            if status is not None and row["application_status"] != status.value:
                continue
            rows.append(row)
    rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return rows


@router.get("/{job_id}")
async def get_job(
    job_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    await authorize_owner(session, principal, job.user_id, track=job.track)
    row = await _job_row(session, job)
    cv = await _cv_for(session, job.id)
    cover = (await session.execute(
        select(CoverLetter).where(CoverLetter.job_id == job.id)
    )).scalar_one_or_none()
    app = await _application_for(session, job.id)
    outreach = list((await session.execute(
        select(Outreach).where(Outreach.application_id == app.id) if app
        else select(Outreach).where(Outreach.application_id == job.id)
    )).scalars().all()) if app else []
    thread_msgs: list[dict] = []
    if app:
        threads = list((await session.execute(
            select(Thread).where(Thread.application_id == app.id)
        )).scalars().all())
        for t in threads:
            for r in (await session.execute(
                select(Reply).where(Reply.thread_id == t.id).order_by(Reply.created_at)
            )).scalars().all():
                thread_msgs.append({"direction": r.direction.value, "from": r.from_addr,
                                    "subject": r.subject, "body": r.body,
                                    "classification": r.classification.value if r.classification else None})
    audit = await app_repo.list_audit(session, user_id=job.user_id, application_id=app.id) if app else []

    row.update({
        "description": job.description,
        "cv": ({"pdf_url": cv.pdf_url, "ats_score": cv.ats_score,
                "ats_breakdown": cv.ats_breakdown} if cv else None),
        "cover_letter": ({"pdf_url": cover.pdf_url, "body": cover.body} if cover else None),
        "application": ({"id": str(app.id), "status": app.status.value,
                         "tracker_status": app.tracker_status.value,
                         "application_status": app.tracker_status.value,
                         "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None} if app else None),
        "outreach": [{"id": str(o.id), "step": o.sequence_step.value,
                      "status": o.status.value, "subject": o.subject} for o in outreach],
        "thread": thread_msgs,
        "audit": [{"kind": e.kind, "actor": e.actor, "detail": e.detail,
                   "created_at": e.created_at.isoformat()} for e in audit],
    })
    return row


@router.patch("/{job_id}/application-status")
async def update_job_application_status(
    job_id: UUID,
    body: ApplicationStatusUpdate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Set application tracker status — creates an application on first manual update."""
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    if body.status is TrackerStatus.not_applied:
        raise ConflictError(
            "not_applied is only shown for jobs that have not been tracked yet"
        )
    va_id = await authorize_owner(
        session, principal, job.user_id, track=job.track
    )
    app = await _application_for(session, job.id)
    cv = await _cv_for(session, job.id)
    if app is None:
        app = Application(
            user_id=job.user_id,
            job_id=job.id,
            generated_cv_id=cv.id if cv else None,
            va_id=va_id,
            status=ApplicationStatus.submitted,
            tracker_status=body.status,
            submitted_at=datetime.now(timezone.utc),
        )
        session.add(app)
        if job.status in (JobStatus.ready, JobStatus.scored):
            job.status = JobStatus.submitted
        app_repo.record_event(
            session,
            application=app,
            kind="status_set",
            actor=_actor(principal),
            detail={"status": body.status.value, "created": True},
        )
    else:
        await app_repo.set_tracker_status(
            session,
            application=app,
            status=body.status,
            actor=_actor(principal),
        )
    await session.flush()
    return await _job_row(session, job)


@router.patch("/{job_id}/track")
async def override_track(
    job_id: UUID,
    body: TrackOverrideRequest,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    await authorize_owner(session, principal, job.user_id, track=job.track)
    job.track_override = body.track
    job.track = body.track
    await session.flush()
    return await _job_row(session, job)


@router.post("/{job_id}/generate", response_model=GenerateResponse)
async def generate(
    job_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Run classify -> score -> tailor + render synchronously (dashboard action)."""
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    await authorize_owner(session, principal, job.user_id, track=job.track)
    track = service.classify_track(job)
    profile = await profiles_repo.get_by_user_track(session, user_id=job.user_id, track=track)
    if profile is None:
        raise ConflictError(f"No master profile for track '{track.value}'")
    job = await service.score_relevance(session, job=job, profile=profile)
    if job.status is JobStatus.rejected:
        return GenerateResponse(job_id=job.id, status=job.status)
    cv = await service.generate_cv(session, job=job, profile=profile)
    return GenerateResponse(
        job_id=job.id, status=job.status, generated_cv_id=cv.id, pdf_url=cv.pdf_url
    )


@router.post("/{job_id}/submit", response_model=SubmitResponse)
async def submit(
    job_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> SubmitResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    # Owning hunter, or a VA assigned to this hunter+track. Returns the va_id to stamp.
    va_id = await authorize_owner(session, principal, job.user_id, track=job.track)
    if job.status is not JobStatus.ready:
        raise ConflictError(f"Job not ready to submit (status={job.status.value})")
    cv = (
        await session.execute(
            select(GeneratedCv).where(GeneratedCv.job_id == job.id)
        )
    ).scalar_one_or_none()
    if cv is None:
        raise ConflictError("No generated CV for this job")
    application = await service.submit_application(
        session, user_id=job.user_id, job=job, generated_cv=cv, va_id=va_id
    )
    return SubmitResponse(application_id=application.id, status=application.status.value)

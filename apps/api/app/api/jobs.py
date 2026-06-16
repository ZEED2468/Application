"""Jobs API — hunter-scoped list/detail, track override, generate CV, VA submit."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import JobStatus, Origin, PrincipalType, Track
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db import get_session
from app.deps import Principal, current_principal, current_user
from app.models.application import Application
from app.models.cover_letter import CoverLetter
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.reply import Reply
from app.models.thread import Thread
from app.models.user import User
from app.models.va_assignment import VaAssignment
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


async def _cv_for(session, job_id):
    return (await session.execute(
        select(GeneratedCv).where(GeneratedCv.job_id == job_id)
    )).scalar_one_or_none()


async def _application_for(session, job_id):
    return (await session.execute(
        select(Application).where(Application.job_id == job_id)
    )).scalar_one_or_none()


async def _job_row(session, job: Job) -> dict:
    cv = await _cv_for(session, job.id)
    app = await _application_for(session, job.id)
    return {
        "id": str(job.id), "company": job.company, "title": job.title,
        "role_title": job.role_title, "location": job.location, "url": job.url,
        "track": (job.track.value if job.track else None),
        "track_override": (job.track_override.value if job.track_override else None),
        "origin": job.origin.value, "status": job.status.value,
        "relevance_score": job.relevance_score,
        "ats_score": cv.ats_score if cv else None,
        "application_id": str(app.id) if app else None,
        "tracker_status": app.tracker_status.value if app else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("")
async def list_jobs(
    status: JobStatus | None = Query(default=None),
    track: Track | None = Query(default=None),
    origin: Origin | None = Query(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    jobs = await jobs_repo.list_for_user(session, user_id=user.id, status=status)
    rows = []
    for j in jobs:
        if track is not None and j.track != track:
            continue
        if origin is not None and j.origin != origin:
            continue
        rows.append(await _job_row(session, j))
    return rows


@router.get("/{job_id}")
async def get_job(
    job_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await jobs_repo.get_owned(session, user_id=user.id, job_id=job_id)
    if job is None:
        raise NotFoundError("Job not found")
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
    audit = await app_repo.list_audit(session, user_id=user.id, application_id=app.id) if app else []

    row.update({
        "description": job.description,
        "cv": ({"pdf_url": cv.pdf_url, "ats_score": cv.ats_score,
                "ats_breakdown": cv.ats_breakdown} if cv else None),
        "cover_letter": ({"pdf_url": cover.pdf_url, "body": cover.body} if cover else None),
        "application": ({"id": str(app.id), "status": app.status.value,
                         "tracker_status": app.tracker_status.value} if app else None),
        "outreach": [{"id": str(o.id), "step": o.sequence_step.value,
                      "status": o.status.value, "subject": o.subject} for o in outreach],
        "thread": thread_msgs,
        "audit": [{"kind": e.kind, "actor": e.actor, "detail": e.detail,
                   "created_at": e.created_at.isoformat()} for e in audit],
    })
    return row


@router.patch("/{job_id}/track")
async def override_track(
    job_id: UUID,
    body: TrackOverrideRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await jobs_repo.get_owned(session, user_id=user.id, job_id=job_id)
    if job is None:
        raise NotFoundError("Job not found")
    job.track_override = body.track
    job.track = body.track
    await session.flush()
    return await _job_row(session, job)


@router.post("/{job_id}/generate", response_model=GenerateResponse)
async def generate(
    job_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> GenerateResponse:
    """Run classify -> score -> tailor + render synchronously (dashboard action)."""
    job = await jobs_repo.get_owned(session, user_id=user.id, job_id=job_id)
    if job is None:
        raise NotFoundError("Job not found")
    track = service.classify_track(job)
    profile = await profiles_repo.get_by_user_track(session, user_id=user.id, track=track)
    if profile is None:
        raise ConflictError(f"No master profile for track '{track.value}'")
    job = await service.score_relevance(session, job=job, profile=profile)
    if job.status is JobStatus.rejected:
        return GenerateResponse(job_id=job.id, status=job.status)
    cv = await service.generate_cv(session, job=job, profile=profile)
    return GenerateResponse(
        job_id=job.id, status=job.status, generated_cv_id=cv.id, pdf_url=cv.pdf_url
    )


async def _authorize_submit(session: AsyncSession, principal: Principal, job) -> UUID | None:
    """Owning hunter, or a VA assigned to this hunter+track, may submit.
    Returns the va_id to stamp (None for hunter submits)."""
    if principal.type is PrincipalType.user:
        if job.user_id != principal.id:
            raise ForbiddenError("Not your job")
        return None
    # VA: must have an assignment covering this hunter (and track, or all-tracks).
    stmt = select(VaAssignment).where(
        VaAssignment.va_id == principal.id, VaAssignment.user_id == job.user_id
    )
    assignments = (await session.execute(stmt)).scalars().all()
    if not any(a.track is None or a.track == job.track for a in assignments):
        raise ForbiddenError("VA not assigned to this hunter/track")
    return principal.id


@router.post("/{job_id}/submit", response_model=SubmitResponse)
async def submit(
    job_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> SubmitResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    va_id = await _authorize_submit(session, principal, job)
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

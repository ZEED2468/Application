"""Jobs API — hunter-scoped list/detail, track override, generate CV, VA submit."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import JobStatus, PrincipalType
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.db import get_session
from app.deps import Principal, current_principal, current_user
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.user import User
from app.models.va_assignment import VaAssignment
from app.pipelines.apply import service
from app.repositories import jobs as jobs_repo
from app.repositories import profiles as profiles_repo
from app.schemas.jobs import (
    GenerateResponse,
    JobOut,
    SubmitResponse,
    TrackOverrideRequest,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: JobStatus | None = Query(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[JobOut]:
    jobs = await jobs_repo.list_for_user(session, user_id=user.id, status=status)
    return [JobOut.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    job = await jobs_repo.get_owned(session, user_id=user.id, job_id=job_id)
    if job is None:
        raise NotFoundError("Job not found")
    return JobOut.model_validate(job)


@router.patch("/{job_id}/track", response_model=JobOut)
async def override_track(
    job_id: UUID,
    body: TrackOverrideRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    job = await jobs_repo.get_owned(session, user_id=user.id, job_id=job_id)
    if job is None:
        raise NotFoundError("Job not found")
    job.track_override = body.track
    job.track = body.track
    await session.flush()
    return JobOut.model_validate(job)


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

"""Pipeline A orchestration: discover -> score+classify -> generate CV -> submit.

Each step is a plain async function so it can be driven by a Celery consumer in
prod or called directly in tests. `emit` is injected (defaults to the real bus)
so unit tests can capture events without a live broker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog

from app.core.enums import ApplicationStatus, CvStatus, JobStatus
from app.events import names
from app.events.bus import emit as _real_emit
from app.events.contracts import (
    ApplicationSubmitted,
    CvGenerated,
    JobDiscovered,
    JobScored,
)
from app.llm import relevance, tailoring, track_classify
from app.models.application import Application
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply import render
from app.repositories import jobs as jobs_repo
from app.repositories import profiles as profiles_repo
from app.sources import active_sources
from app.sources.base import SourceQuery
from app.sources.normalize import to_job_fields

log = structlog.get_logger(__name__)


def _emphasis_keywords(profile: MasterProfile) -> list[str]:
    return tailoring._flatten_skills(profile.skills)[:8]


async def discover_for_user(
    session, *, user_id: UUID, profile: MasterProfile, boards: list[str] | None = None,
    emit=_real_emit,
) -> list[Job]:
    """Run active sources for the hunter's track, dedupe-insert, emit job.discovered."""
    query = SourceQuery(
        track=profile.track,
        keywords=_emphasis_keywords(profile),
        boards=boards or [],
    )
    new_jobs: list[Job] = []
    for source in active_sources():
        if not source.supports(profile.track):
            continue
        async for raw in source.fetch(query):
            job = await jobs_repo.insert_if_new(
                session, user_id=user_id, fields=to_job_fields(raw)
            )
            if job is not None:
                new_jobs.append(job)
                emit(names.JOB_DISCOVERED,
                     JobDiscovered(user_id=user_id, job_id=job.id, source=job.source.value))
    log.info("apply.discovered", count=len(new_jobs), track=profile.track.value)
    return new_jobs


def classify_track(job: Job) -> Track:
    """Assign a track from the JD text (override-able later). Track is needed
    before scoring/tailoring because the master profile is per (user, track)."""
    track = job.track_override or track_classify.classify(
        title=job.title, description=job.description
    )
    job.track = track
    return track


async def score_relevance(session, *, job: Job, profile: MasterProfile, emit=_real_emit) -> Job:
    """Relevance prefilter against the track's profile. Emits job.scored if it passes."""
    skills = tailoring._flatten_skills(profile.skills)
    job.relevance_score = relevance.score(
        title=job.title, description=job.description, skills=skills
    )
    if not relevance.passes(job.relevance_score):
        job.status = JobStatus.rejected
        log.info("apply.rejected", job_id=str(job.id), score=job.relevance_score)
        return job
    job.status = JobStatus.scored
    await session.flush()
    emit(names.JOB_SCORED,
         JobScored(user_id=job.user_id, job_id=job.id,
                   relevance_score=job.relevance_score, track=job.track))
    return job


async def generate_cv(session, *, job: Job, profile: MasterProfile, emit=_real_emit) -> GeneratedCv:
    """Tailor (truth-bounded) -> render PDF -> store in R2 -> emit cv.generated."""
    from app.integrations import r2

    job.status = JobStatus.tailoring
    cv_json, diff = await tailoring.tailor(
        profiles_repo.profile_to_dict(profile),
        job_title=job.title, job_description=job.description,
    )
    owner = await session.get(User, job.user_id)
    name = owner.name if owner else (profile.headline or "Candidate")
    tex = render.build_tex(cv_json, name=name)
    pdf = await render.render_pdf(tex)

    tex_key = f"{job.user_id}/{job.id}/cv.tex"
    pdf_key = f"{job.user_id}/{job.id}/cv.pdf"
    await r2.put_bytes(tex_key, tex.encode(), "application/x-tex")
    pdf_url = await r2.put_bytes(pdf_key, pdf, "application/pdf")

    cv = GeneratedCv(
        user_id=job.user_id, job_id=job.id, master_profile_id=profile.id,
        cv_json=cv_json, latex_source=tex, tex_key=tex_key, pdf_key=pdf_key,
        pdf_url=pdf_url, tailoring_diff=diff, status=CvStatus.ready,
    )
    session.add(cv)
    job.status = JobStatus.ready
    await session.flush()
    emit(names.CV_GENERATED,
         CvGenerated(user_id=job.user_id, job_id=job.id, generated_cv_id=cv.id))
    return cv


async def submit_application(
    session, *, user_id: UUID, job: Job, generated_cv: GeneratedCv,
    va_id: UUID | None = None, emit=_real_emit,
) -> Application:
    """VA submits the application -> emits application.submitted (kicks off Pipeline B)."""
    application = Application(
        user_id=user_id, job_id=job.id, generated_cv_id=generated_cv.id, va_id=va_id,
        status=ApplicationStatus.submitted, submitted_at=datetime.now(timezone.utc),
    )
    session.add(application)
    job.status = JobStatus.submitted
    await session.flush()
    emit(names.APPLICATION_SUBMITTED,
         ApplicationSubmitted(user_id=user_id, application_id=application.id,
                              job_id=job.id, track=job.track))
    return application

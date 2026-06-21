"""Pipeline A orchestration: discover -> score+classify -> generate CV -> submit.

Each step is a plain async function so it can be driven by a Celery consumer in
prod or called directly in tests. `emit` is injected (defaults to the real bus)
so unit tests can capture events without a live broker.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog

from app.config import settings
from app.core.enums import ApplicationStatus, CvStatus, JobSourceName, JobStatus
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
from app.repositories import source_boards as boards_repo
from app.sources import active_sources
from app.sources.base import SourceQuery
from app.sources.normalize import to_job_fields

log = structlog.get_logger(__name__)


def _emphasis_keywords(profile: MasterProfile) -> list[str]:
    return tailoring._flatten_skills(profile.skills)[:8]


_BOARD_SOURCE_NAMES = {JobSourceName.greenhouse, JobSourceName.lever, JobSourceName.ashby}


def _config_note(name: JobSourceName, boards: list[str]) -> str | None:
    """Why a source found nothing, config-wise — so the diagnostics distinguish
    'skipped: not configured' from 'ran: 0 results'."""
    if name is JobSourceName.adzuna and not (settings.adzuna_app_id and settings.adzuna_app_key):
        return "no ADZUNA_APP_ID/ADZUNA_APP_KEY in this environment"
    if name is JobSourceName.serpapi and not settings.serpapi_api_key:
        return "no SERPAPI_API_KEY in this environment"
    if name in _BOARD_SOURCE_NAMES and not boards:
        return "no board tokens — add company slugs in Admin -> Job boards"
    return None


async def _run_sources(
    session, *, user_id: UUID, profile: MasterProfile, boards: list[str] | None = None,
    emit=_real_emit,
) -> tuple[list[Job], list[dict]]:
    """Run active sources for the hunter's track; dedupe-insert; emit job.discovered.

    Each source is isolated in try/except so one failing source (or a missing
    `source_board` table) can never kill the whole run. Returns the new jobs plus a
    per-source report for the on-demand diagnostics endpoint.
    """
    query = SourceQuery(
        track=profile.track,
        keywords=_emphasis_keywords(profile),
        boards=boards or [],
    )
    actives = [s for s in active_sources() if s.supports(profile.track)]
    log.info("discover.start", user_id=str(user_id), track=profile.track.value,
             keywords=query.keywords, fake_mode=settings.use_fake_integrations,
             sources=[s.name.value for s in actives])

    # Board scrapers (Greenhouse/Lever/Ashby) pull per-company tokens. Resilient: a
    # missing/un-migrated `source_board` table must not break discovery.
    by_source: dict = {}
    if boards is None:
        try:
            by_source = await boards_repo.active_by_source(session)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            log.warning("discover.boards_lookup_failed", error=str(exc),
                        exc_type=type(exc).__name__)

    new_jobs: list[Job] = []
    report: list[dict] = []
    for source in actives:
        name = source.name.value
        if boards is None:
            query.boards = by_source.get(source.name, [])
        # Notes are diagnostic and only meaningful with real integrations.
        note = (
            None if settings.use_fake_integrations
            else _config_note(source.name, query.boards)
        )
        found = inserted = 0
        error: str | None = None
        log.info("discover.source.fetch", source=name, boards=query.boards or None, note=note)
        try:
            # Unconfigured adapters (no key / no board tokens) no-op immediately.
            async for raw in source.fetch(query):
                found += 1
                job = await jobs_repo.insert_if_new(
                    session, user_id=user_id, fields=to_job_fields(raw)
                )
                if job is not None:
                    inserted += 1
                    new_jobs.append(job)
                    emit(names.JOB_DISCOVERED,
                         JobDiscovered(user_id=user_id, job_id=job.id, source=name))
        except Exception as exc:  # noqa: BLE001 — one bad source shouldn't stop the rest
            error = f"{type(exc).__name__}: {exc}"
            log.warning("discover.source.failed", source=name, error=error)
        log.info("discover.source.done", source=name, found=found, inserted=inserted,
                 error=error, note=note)
        report.append({"source": name, "found": found, "inserted": inserted,
                       "error": error, "note": note})
    log.info("discover.done", user_id=str(user_id), track=profile.track.value,
             new=len(new_jobs))
    return new_jobs, report


async def discover_for_user(
    session, *, user_id: UUID, profile: MasterProfile, boards: list[str] | None = None,
    emit=_real_emit,
) -> list[Job]:
    """Run active sources for the hunter's track, dedupe-insert, emit job.discovered."""
    new_jobs, _ = await _run_sources(
        session, user_id=user_id, profile=profile, boards=boards, emit=emit
    )
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
    """Tailor + ATS + cover letter via the SHARED engine (same path as manual)."""
    from app.pipelines import generation

    owner = await session.get(User, job.user_id)
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=owner, emit=emit
    )
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

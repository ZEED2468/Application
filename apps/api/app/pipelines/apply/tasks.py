"""Pipeline A (Apply) consumers + internal tasks. Seam for Engineer 1.

job.discovered -> classify track -> score relevance -> (if pass) tailor + render
-> CV ready for VA submit. poll_sources is the beat entrypoint that discovers.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.enums import UserRole
from app.events.names import JOB_DISCOVERED
from app.models.user import User
from app.pipelines.apply import service
from app.repositories import jobs as jobs_repo
from app.repositories import profiles as profiles_repo
from app.workers.celery_app import UserScopedTask, celery_app
from app.workers.runner import run_with_session

log = structlog.get_logger(__name__)


@celery_app.task(name=JOB_DISCOVERED, base=UserScopedTask, bind=True)
def on_job_discovered(self, payload: dict) -> None:
    """Classify -> score -> generate CV for a newly discovered job."""
    user_id = UUID(payload["user_id"])
    job_id = UUID(payload["job_id"])

    async def _work(session):
        job = await jobs_repo.get_owned(session, user_id=user_id, job_id=job_id)
        if job is None:
            return
        track = service.classify_track(job)
        profile = await profiles_repo.get_by_user_track(session, user_id=user_id, track=track)
        if profile is None:
            log.warning("apply.no_profile", track=track.value, user_id=str(user_id))
            return
        job = await service.score_relevance(session, job=job, profile=profile)
        if job.status.value == "scored":
            await service.generate_cv(session, job=job, profile=profile)

    run_with_session(_work)


@celery_app.task(name="task.apply.poll_sources", bind=True)
def poll_sources(self) -> None:
    """Beat: for every active hunter and each of their track profiles, discover jobs."""

    async def _work(session):
        users = (
            await session.execute(
                select(User).where(User.is_active.is_(True), User.role == UserRole.hunter)
            )
        ).scalars().all()
        total = 0
        for user in users:
            profiles = (
                await session.execute(
                    select(profiles_repo.MasterProfile).where(
                        profiles_repo.MasterProfile.user_id == user.id
                    )
                )
            ).scalars().all()
            for profile in profiles:
                new_jobs = await service.discover_for_user(
                    session, user_id=user.id, profile=profile
                )
                total += len(new_jobs)
        log.info("apply.poll_sources.done", discovered=total)

    run_with_session(_work)

"""POST /cv/runs/job/{id} — run the engine for a job (format check) + cv_run on job detail.

Exercises the route functions directly (the auth + build-from-profile + job-link logic),
avoiding an ASGI round-trip.
"""

from sqlalchemy import select

from app.api.cv_runs import create_cv_run_for_job
from app.api.jobs import get_job
from app.core.enums import JobSourceName, JobStatus, Origin, PrincipalType, Track
from app.cv_engine.runs.models import CvRun
from app.deps import Principal
from app.models.job import Job
from tests.helpers import seed_hunter


def _principal(user) -> Principal:
    return Principal(id=user.id, type=PrincipalType.user, role="hunter", track_scope=[])


async def _job(session, user) -> Job:
    job = Job(
        user_id=user.id, source=JobSourceName.manual, origin=Origin.manual, dedupe_key="dk-cv",
        company="Streamline", title="Senior Backend Engineer", role_title="Senior Backend Engineer",
        description="Need Go and Kubernetes. Postgres required.",
        track=Track.backend, status=JobStatus.scored,
    )
    session.add(job)
    await session.flush()
    return job


async def test_run_for_job_builds_from_profile_and_links_job(session):
    user, _ = await seed_hunter(session)  # backend profile + parsed RoleCv (passes the gate)
    job = await _job(session, user)

    result = await create_cv_run_for_job(job.id, _principal(user), session)

    assert result["run_id"]
    assert result["state"] in ("released", "needs_review")
    assert {"fixed", "resolved", "failed", "blocking", "violation_count"} <= result["delta"].keys()
    run = (await session.execute(select(CvRun).where(CvRun.job_id == job.id))).scalar_one()
    assert run.job_id == job.id
    assert run.input["cv_json"]["skills"]  # built from the profile (skills flattened to a list)


async def test_job_detail_carries_latest_cv_run(session):
    user, _ = await seed_hunter(session)
    job = await _job(session, user)
    assert (await get_job(job.id, _principal(user), session))["cv_run"] is None  # none yet

    await create_cv_run_for_job(job.id, _principal(user), session)

    detail = await get_job(job.id, _principal(user), session)
    assert detail["cv_run"] is not None
    assert detail["cv_run"]["state"] in ("released", "needs_review")

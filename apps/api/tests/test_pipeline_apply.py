"""Pipeline A end-to-end against the fake source/LLM/R2, capturing emitted events.

discover -> classify -> score -> tailor+render -> store -> submit, asserting DB
state transitions and that the right events fire (the seam into Pipeline B).
"""

import pytest

from app.core.enums import ApplicationStatus, CvStatus, JobStatus, Track, UserRole
from app.events import names
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply import service
from app.security import hash_password


class EventSink:
    def __init__(self):
        self.events = []

    def __call__(self, name, payload):
        self.events.append((name, payload))

    def names(self):
        return [n for n, _ in self.events]


async def _seed(session):
    user = User(
        email="h@example.com", password_hash=hash_password("x"),
        name="Hunter One", role=UserRole.hunter,
    )
    session.add(user)
    await session.flush()
    profile = MasterProfile(
        user_id=user.id, track=Track.backend, headline="Backend engineer",
        summary="I build production backend systems.",
        skills=["Go", "NestJS", "Kubernetes", "microservices", "distributed", "Postgres"],
        experience=[{"title": "Backend Engineer", "company": "Streamline",
                     "bullets": ["Built Go microservices", "Ran Kubernetes"]}],
        projects=[{"name": "Queue", "description": "A Go task queue"}],
        education=[], links={},
    )
    session.add(profile)
    await session.flush()
    return user, profile


@pytest.mark.asyncio
async def test_full_apply_chain(session):
    user, profile = await _seed(session)
    sink = EventSink()

    # 1. Discover via the fake source.
    new_jobs = await service.discover_for_user(
        session, user_id=user.id, profile=profile, emit=sink
    )
    assert new_jobs, "fake source should yield backend jobs"
    assert names.JOB_DISCOVERED in sink.names()
    job = new_jobs[0]

    # 2. Classify track + 3. score relevance.
    service.classify_track(job)
    assert job.track is Track.backend
    job = await service.score_relevance(session, job=job, profile=profile, emit=sink)
    assert job.status is JobStatus.scored
    assert names.JOB_SCORED in sink.names()

    # 4. Tailor + render + store.
    cv = await service.generate_cv(session, job=job, profile=profile, emit=sink)
    assert cv.status is CvStatus.ready
    assert cv.pdf_url and cv.tex_key
    assert job.status is JobStatus.ready
    assert names.CV_GENERATED in sink.names()

    # 5. VA submit -> application.submitted (seam into Pipeline B).
    app_row = await service.submit_application(
        session, user_id=user.id, job=job, generated_cv=cv, emit=sink
    )
    assert app_row.status is ApplicationStatus.submitted
    assert job.status is JobStatus.submitted
    assert names.APPLICATION_SUBMITTED in sink.names()

    # The emitted payload is the frozen contract type, carrying user_id + job_id.
    from app.events.contracts import ApplicationSubmitted
    payload = sink.events[-1][1]
    assert isinstance(payload, ApplicationSubmitted)
    assert payload.user_id == user.id and payload.job_id == job.id


@pytest.mark.asyncio
async def test_discover_is_idempotent(session):
    user, profile = await _seed(session)
    sink = EventSink()
    first = await service.discover_for_user(session, user_id=user.id, profile=profile, emit=sink)
    second = await service.discover_for_user(session, user_id=user.id, profile=profile, emit=sink)
    assert first and not second  # same jobs -> deduped on re-poll

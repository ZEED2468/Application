"""Seed helpers + an event sink for service-level tests."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import ApplicationStatus, JobSourceName, JobStatus, Origin, Track, UserRole
from app.models.application import Application
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.models.va import Va
from app.models.va_assignment import VaAssignment
from app.security import hash_password


class EventSink:
    def __init__(self):
        self.events = []

    def __call__(self, name, payload):
        self.events.append((name, payload))

    def names(self):
        return [n for n, _ in self.events]


async def seed_hunter(session, *, track=Track.backend) -> tuple[User, MasterProfile]:
    user = User(email=f"h-{track.value}@ex.com", password_hash=hash_password("x"),
                name="Hunter One", role=UserRole.hunter)
    session.add(user)
    await session.flush()
    profile = MasterProfile(
        user_id=user.id, track=track, headline="Backend engineer",
        summary="I build production backend systems.",
        skills=["Go", "Kubernetes", "microservices", "distributed", "Postgres"],
        experience=[{"title": "Backend Engineer", "company": "Streamline",
                     "bullets": ["Built Go microservices", "Ran Kubernetes clusters"]}],
        projects=[{"name": "Queue", "description": "A Go task queue"}],
        education=[], links={"backend": "https://demo.example/backend"},
    )
    session.add(profile)
    await session.flush()
    return user, profile


async def seed_va(session, *, user, track=None) -> Va:
    va = Va(name="VA Vera", email="vera@ex.com", password_hash=hash_password("x"),
            whatsapp_jid="2348000000000@s.whatsapp.net")
    session.add(va)
    await session.flush()
    session.add(VaAssignment(va_id=va.id, user_id=user.id, track=track))
    await session.flush()
    return va


async def seed_submitted_application(session, *, user, track=Track.backend) -> Application:
    job = Job(
        user_id=user.id, source=JobSourceName.greenhouse, origin=Origin.auto,
        dedupe_key=f"dk-{user.id}", company="Streamline", title="Backend Engineer",
        role_title="Backend Engineer", description="Go microservices, distributed, kubernetes",
        track=track, status=JobStatus.submitted,
    )
    session.add(job)
    await session.flush()
    app = Application(user_id=user.id, job_id=job.id, status=ApplicationStatus.submitted,
                      submitted_at=datetime.now(timezone.utc))
    session.add(app)
    await session.flush()
    return app

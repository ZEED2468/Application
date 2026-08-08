"""Track entity: readiness, lifecycle (create/archive), resume duplicate, and the
AI feature guard that blocks generation on a track with no resume."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import (
    JobSourceName, JobStatus, Origin, ParseStatus, Track, UserRole,
)
from app.db import get_session
from app.main import app
from app.models import Base
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.security import hash_password

HUNTER = {"email": "hunter@example.com", "password": "s3cretpw"}


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(User(email=HUNTER["email"], password_hash=hash_password(HUNTER["password"]),
                   name="Hunter One", role=UserRole.hunter))
        await s.commit()

    async def _override():
        async with maker() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c, maker
    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client) -> UUID:
    r = await client.post("/api/auth/login", json=HUNTER)
    assert r.status_code == 200, r.text
    return UUID(r.json()["id"])


async def _seed_cv(maker, uid, track=Track.backend):
    async with maker() as s:
        s.add(RoleCv(user_id=uid, track=track, original_filename="cv.pdf",
                     source_file_key=f"{uid}/role-cv/{track.value}/source.pdf",
                     parse_status=ParseStatus.parsed))
        s.add(MasterProfile(user_id=uid, track=track, headline="Backend engineer",
                            summary="I build backends.", skills=["Go"], experience=[],
                            education=[], projects=[], links={}, target_roles=["Backend Engineer"],
                            confirmed=True))
        await s.commit()


@pytest.mark.asyncio
async def test_tracks_readiness(ctx):
    client, maker = ctx
    uid = await _login(client)
    await _seed_cv(maker, uid, Track.backend)
    # a track with a profile but no CV -> setup_required
    async with maker() as s:
        s.add(MasterProfile(user_id=uid, track=Track.frontend, skills=[], experience=[],
                            education=[], projects=[], links={}, confirmed=False))
        await s.commit()

    r = await client.get("/api/tracks")
    assert r.status_code == 200, r.text
    by_slug = {t["slug"]: t for t in r.json()}
    assert by_slug["backend"]["status"] == "ready" and by_slug["backend"]["resume"] is True
    assert by_slug["frontend"]["status"] == "setup_required" and by_slug["frontend"]["resume"] is False
    # each track got a stable id (backfilled)
    assert by_slug["backend"]["id"] and by_slug["frontend"]["id"]


@pytest.mark.asyncio
async def test_create_rename_archive(ctx):
    client, _ = ctx
    await _login(client)
    created = await client.post("/api/tracks", json={"name": "Data Science"})
    assert created.status_code == 200, created.text
    t = created.json()
    assert t["slug"] == "data-science" and t["status"] == "setup_required" and t["resume"] is False
    tid = t["id"]

    dup = await client.post("/api/tracks", json={"name": "Data Science"})
    assert dup.status_code == 400 and dup.json()["code"] == "track_exists"

    renamed = await client.patch(f"/api/tracks/{tid}", json={"name": "ML Engineering"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "ML Engineering"

    arch = await client.post(f"/api/tracks/{tid}/archive")
    assert arch.status_code == 200 and arch.json()["status"] == "archived"
    un = await client.post(f"/api/tracks/{tid}/unarchive")
    assert un.status_code == 200 and un.json()["status"] == "setup_required"


@pytest.mark.asyncio
async def test_guard_blocks_generate_without_resume(ctx):
    client, maker = ctx
    uid = await _login(client)
    async with maker() as s:
        job = Job(user_id=uid, source=JobSourceName.manual, origin=Origin.manual,
                  dedupe_key="dk-guard", company="Acme", title="Backend Engineer",
                  role_title="Backend Engineer", description="Go", track=Track.backend,
                  status=JobStatus.scored)
        s.add(job)
        await s.flush()
        job_id = job.id
        await s.commit()

    blocked = await client.post(f"/api/jobs/{job_id}/generate")
    assert blocked.status_code == 400, blocked.text
    body = blocked.json()
    assert body["code"] == "track_not_ready"
    assert body["action"]["label"] == "Upload CV"
    assert body["action"]["route"] == "/profile?track=backend"

    # once a resume exists for the track, the guard no longer blocks generation
    await _seed_cv(maker, uid, Track.backend)
    ok = await client.post(f"/api/jobs/{job_id}/generate")
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_duplicate_resume_from_another_track(ctx):
    client, maker = ctx
    uid = await _login(client)
    await _seed_cv(maker, uid, Track.backend)  # source has a CV

    # create an empty target track
    target = (await client.post("/api/tracks", json={"name": "general"})).json()
    tracks = (await client.get("/api/tracks")).json()
    source = next(t for t in tracks if t["slug"] == "backend")

    assert target["resume"] is False
    dup = await client.post(f"/api/tracks/{target['id']}/resume/from/{source['id']}")
    assert dup.status_code == 200, dup.text
    assert dup.json()["resume"] is True and dup.json()["status"] == "ready"

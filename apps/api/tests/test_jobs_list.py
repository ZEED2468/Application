"""Jobs list endpoint: the page-size cap must accept the dashboard's broad fetch.

The web dashboard fetches the whole list once (`list({}, 1, 500)`) and filters/paginates
client-side, so `page_size=500` must be a valid request (it used to 422 at the old le=100
cap, which blanked the jobs page). Anything above the cap is still rejected.
"""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import JobSourceName, JobStatus, Origin, Track, UserRole
from app.db import get_session
from app.main import app
from app.models import Base
from app.models.job import Job
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


async def _seed_job(maker, uid, *, track: Track, company: str) -> None:
    async with maker() as s:
        s.add(Job(
            user_id=uid, source=JobSourceName.manual, origin=Origin.manual,
            dedupe_key=f"dk-{company}", company=company, title=f"{company} Engineer",
            role_title=f"{company} Engineer", description="desc",
            track=track, status=JobStatus.ready,
        ))
        await s.commit()


@pytest.mark.asyncio
async def test_jobs_list_accepts_broad_page_size(ctx):
    client, _ = ctx
    await _login(client)
    r = await client.get("/api/jobs", params={"page_size": 500})
    assert r.status_code == 200, r.text
    assert r.json()["page_size"] == 500


@pytest.mark.asyncio
async def test_jobs_list_rejects_over_cap(ctx):
    client, _ = ctx
    await _login(client)
    r = await client.get("/api/jobs", params={"page_size": 501})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_track_filter_is_case_insensitive(ctx):
    client, maker = ctx
    uid = await _login(client)
    await _seed_job(maker, uid, track=Track.frontend, company="Pixel")
    await _seed_job(maker, uid, track=Track.backend, company="Streamline")
    # Capitalized filter must still match the stored lowercase "frontend".
    r = await client.get("/api/jobs", params={"track": "Frontend"})
    assert r.status_code == 200, r.text
    companies = {row["company"] for row in r.json()["items"]}
    assert companies == {"Pixel"}


@pytest.mark.asyncio
async def test_unknown_track_filter_returns_empty(ctx):
    client, maker = ctx
    uid = await _login(client)
    await _seed_job(maker, uid, track=Track.frontend, company="Pixel")
    r = await client.get("/api/jobs", params={"track": "banana"})
    assert r.status_code == 200, r.text
    assert r.json()["items"] == [] and r.json()["total"] == 0
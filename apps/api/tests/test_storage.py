"""R2 storage: fake roundtrip + auth-scoped presigned/streamed downloads + upload validation."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import (
    CvStatus, JobSourceName, JobStatus, Origin, ParseStatus, Track, UserRole,
)
from app.db import get_session
from app.integrations import r2
from app.main import app
from app.models import Base
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.role_cv import RoleCv
from app.models.user import User
from app.security import hash_password

HUNTER = {"email": "hunter@example.com", "password": "s3cretpw"}


@pytest.mark.asyncio
async def test_r2_fake_roundtrip():
    key = "test/roundtrip/sample.bin"
    url = await r2.put_bytes(key, b"hello-cv", "application/octet-stream")
    assert url.startswith("file://")
    assert await r2.get_bytes(key) == b"hello-cv"
    assert await r2.get_bytes("nope/missing.bin") is None
    assert r2.presigned_url(key) is None  # fake mode -> no presigned url


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(User(email=HUNTER["email"], password_hash=hash_password(HUNTER["password"]),
                   name="Hunter", role=UserRole.hunter))
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


async def _login(client, email=HUNTER["email"], password=HUNTER["password"]) -> UUID:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return UUID(r.json()["id"])


@pytest.mark.asyncio
async def test_role_cv_upload_validation_and_download(ctx):
    client, maker = ctx
    uid = await _login(client)

    # wrong file type -> 400 (before anything is stored)
    bad = await client.post(
        "/api/onboarding/role-cv",
        data={"track": "backend"},
        files={"file": ("malware.exe", b"x", "application/octet-stream")},
    )
    assert bad.status_code == 400

    # seed a stored CV at its stable key, then download it back
    key = f"{uid}/role-cv/backend/source.pdf"
    await r2.put_bytes(key, b"%PDF-1.4 fake cv", "application/pdf")
    async with maker() as s:
        s.add(RoleCv(user_id=uid, track=Track.backend, original_filename="cv.pdf",
                     source_file_key=key, parse_status=ParseStatus.parsed))
        await s.commit()

    dl = await client.get("/api/onboarding/role-cv/backend/file")
    assert dl.status_code == 200
    assert dl.content == b"%PDF-1.4 fake cv"

    # a track with no upload -> 404
    assert (await client.get("/api/onboarding/role-cv/frontend/file")).status_code == 404


@pytest.mark.asyncio
async def test_job_cv_download_is_auth_scoped(ctx):
    client, maker = ctx
    uid = await _login(client)

    async with maker() as s:
        job = Job(user_id=uid, source=JobSourceName.manual, origin=Origin.manual,
                  dedupe_key="dk-cv", company="Acme", title="Backend Engineer",
                  role_title="Backend Engineer", description="Go", track=Track.backend,
                  status=JobStatus.ready)
        s.add(job)
        await s.flush()
        job_id = job.id
        key = f"{uid}/{job_id}/cv.pdf"
        s.add(GeneratedCv(user_id=uid, job_id=job_id, cv_json={}, pdf_key=key,
                          status=CvStatus.ready))
        # a second, unrelated hunter
        s.add(User(email="other@example.com", password_hash=hash_password("x"),
                   name="Other", role=UserRole.hunter))
        await s.commit()
    await r2.put_bytes(key, b"%PDF tailored", "application/pdf")

    ok = await client.get(f"/api/jobs/{job_id}/cv")
    assert ok.status_code == 200 and ok.content == b"%PDF tailored"

    # owner: no cover letter generated -> 404
    assert (await client.get(f"/api/jobs/{job_id}/cover")).status_code == 404

    # the other hunter cannot reach the CV at all
    await client.post("/api/auth/login", json={"email": "other@example.com", "password": "x"})
    blocked = await client.get(f"/api/jobs/{job_id}/cv")
    assert blocked.status_code in (403, 404)

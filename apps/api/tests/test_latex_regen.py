"""LaTeX templates + regeneration + preview + "Use this template" commit.

Runs in fake mode (no tectonic, no LLM): regeneration takes the deterministic
build_tex fallback and previews return the stub PDF — so these assert the wiring,
auth scoping, and persistence, not the model output.
"""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import JobSourceName, JobStatus, Origin, Track, UserRole
from app.db import get_session
from app.main import app
from app.models import Base
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.latex_template import LatexTemplate
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.security import hash_password

HUNTER = {"email": "hunter@example.com", "password": "s3cretpw"}
CLEAN_TEX = r"\documentclass{article}\begin{document}Hello\end{document}"


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        user = User(email=HUNTER["email"], password_hash=hash_password(HUNTER["password"]),
                    name="Hunter One", role=UserRole.hunter)
        s.add(user)
        await s.flush()
        s.add(MasterProfile(
            user_id=user.id, track=Track.backend, headline="Backend engineer",
            summary="I build production backend systems.",
            skills=["Go", "Kubernetes", "Postgres"],
            experience=[{"title": "Backend Engineer", "company": "Streamline",
                         "bullets": ["Built Go microservices"]}],
            projects=[], education=[], links={},
        ))
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


async def _seed_job(maker, uid, *, dedupe="dk-latex") -> UUID:
    async with maker() as s:
        job = Job(user_id=uid, source=JobSourceName.manual, origin=Origin.manual,
                  dedupe_key=dedupe, company="Acme", title="Backend Engineer",
                  role_title="Backend Engineer", description="Go, Postgres, Kubernetes",
                  track=Track.backend, status=JobStatus.ready)
        s.add(job)
        await s.flush()
        job_id = job.id
        await s.commit()
        return job_id


@pytest.mark.asyncio
async def test_latex_template_roundtrip_per_track(ctx):
    client, maker = ctx
    uid = await _login(client)

    # upload a CV template for backend + a cover template for frontend
    up = await client.post(
        "/api/onboarding/latex-template/upload",
        data={"track": "backend", "kind": "cv"},
        files={"file": ("cv.tex", CLEAN_TEX.encode(), "application/x-tex")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["has_source"] is True
    await client.post(
        "/api/onboarding/latex-template/upload",
        data={"track": "frontend", "kind": "cover"},
        files={"file": ("cover.tex", b"\\documentclass{article}", "application/x-tex")},
    )

    # re-upload backend/cv overwrites (uniqueness on user+track+kind) -> still 2 rows
    await client.post(
        "/api/onboarding/latex-template/upload",
        data={"track": "backend", "kind": "cv"},
        files={"file": ("cv2.tex", b"\\documentclass{book}", "application/x-tex")},
    )
    async with maker() as s:
        rows = (await s.execute(
            select(LatexTemplate).where(LatexTemplate.user_id == uid)
        )).scalars().all()
    assert len(rows) == 2

    # GET single + list reflect what we stored
    got = await client.get("/api/onboarding/latex-template", params={"track": "backend", "kind": "cv"})
    assert got.status_code == 200 and got.json()["source"] == "\\documentclass{book}"
    lst = await client.get("/api/onboarding/latex-templates")
    assert {(r["track"], r["kind"]) for r in lst.json()} == {("backend", "cv"), ("frontend", "cover")}

    # download serves the raw bytes
    dl = await client.get("/api/onboarding/latex-template/backend/cv/file")
    assert dl.status_code == 200 and dl.content == b"\\documentclass{book}"

    # editor save (PUT) updates the source
    put = await client.put("/api/onboarding/latex-template",
                           json={"track": "backend", "kind": "cv", "source": CLEAN_TEX})
    assert put.status_code == 200 and put.json()["source"] == CLEAN_TEX


@pytest.mark.asyncio
async def test_regenerate_returns_compilable_latex(ctx):
    client, maker = ctx
    uid = await _login(client)
    job_id = await _seed_job(maker, uid)

    r = await client.post("/api/latex/regenerate", json={
        "job_id": str(job_id),
        "ats": {"missing_critical": ["Kafka"], "gaps": ["Kafka"], "ai_recommendations": []},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cv_latex"].strip() and body["cover_latex"].strip()
    assert body["cv_compiled"] is True and body["cover_compiled"] is True
    # no uploaded template in this test -> deterministic fallback
    assert body["cv_fell_back"] == "no_template"

    # standalone (no job) still works for a hunter, given a track
    r2 = await client.post("/api/latex/regenerate", json={"track": "backend", "jd_text": "Go role"})
    assert r2.status_code == 200 and r2.json()["cv_latex"].strip()


@pytest.mark.asyncio
async def test_preview_rejects_forbidden_primitives(ctx):
    client, _ = ctx
    await _login(client)

    bad = await client.post("/api/latex/preview",
                            json={"latex": r"\input{/etc/passwd}", "kind": "cv"})
    assert bad.status_code == 400

    ok = await client.post("/api/latex/preview", json={"latex": CLEAN_TEX, "kind": "cv"})
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("application/pdf")


@pytest.mark.asyncio
async def test_from_latex_commit_upserts_generated_cv(ctx):
    client, maker = ctx
    uid = await _login(client)
    job_id = await _seed_job(maker, uid)

    r = await client.post(f"/api/jobs/{job_id}/cv/from-latex", json={"latex": CLEAN_TEX})
    assert r.status_code == 200, r.text
    assert r.json()["resume_doc_url"] == f"/api/jobs/{job_id}/cv"

    async with maker() as s:
        cvs = (await s.execute(
            select(GeneratedCv).where(GeneratedCv.job_id == job_id)
        )).scalars().all()
    assert len(cvs) == 1 and cvs[0].pdf_key and cvs[0].tex_key

    # second commit updates the same row (uq_cv_job), not a duplicate
    again = await client.post(f"/api/jobs/{job_id}/cv/from-latex",
                              json={"latex": CLEAN_TEX + "% v2"})
    assert again.status_code == 200
    async with maker() as s:
        cvs = (await s.execute(
            select(GeneratedCv).where(GeneratedCv.job_id == job_id)
        )).scalars().all()
    assert len(cvs) == 1 and cvs[0].latex_source.endswith("% v2")

    # the committed PDF serves
    dl = await client.get(f"/api/jobs/{job_id}/cv")
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")

    # forbidden primitive -> 400 (sanitiser), never compiled
    bad = await client.post(f"/api/jobs/{job_id}/cover/from-latex",
                            json={"latex": r"\write18{rm -rf /}"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_from_latex_is_auth_scoped(ctx):
    client, maker = ctx
    uid = await _login(client)
    job_id = await _seed_job(maker, uid)

    async with maker() as s:
        s.add(User(email="other@example.com", password_hash=hash_password("x"),
                   name="Other", role=UserRole.hunter))
        await s.commit()

    await client.post("/api/auth/login", json={"email": "other@example.com", "password": "x"})
    blocked = await client.post(f"/api/jobs/{job_id}/cv/from-latex", json={"latex": CLEAN_TEX})
    assert blocked.status_code in (403, 404)

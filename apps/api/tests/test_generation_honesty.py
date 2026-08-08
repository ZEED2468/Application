"""Invariant I2: a CV is only 'ready' when it actually rendered AND parses.

In fake/dev mode the stub render is a known convenience (kept ready). In REAL mode a
failed/unevaluated format gate is a fix-first state — never a blank stub presented as
ready. (Fake-mode readiness is already covered by test_pipeline_apply / test_manual_path.)
"""

import shutil

import pytest

from app.config import settings
from app.core.enums import CvStatus, JobSourceName, JobStatus, Origin, Track, UserRole
from app.cv_engine.render.compile import has_compiler
from app.integrations import r2
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines import generation
from app.pipelines.apply import render
from app.security import hash_password


async def _seed(session):
    user = User(email="g@example.com", password_hash=hash_password("x"),
                name="Grace Hopper", role=UserRole.hunter)
    session.add(user)
    await session.flush()
    profile = MasterProfile(
        user_id=user.id, track=Track.backend, headline="Backend engineer",
        summary="I build production backend systems.",
        skills=["Go", "Kubernetes", "Postgres"],
        experience=[{"title": "Backend Engineer", "company": "Streamline",
                     "bullets": ["Built Go microservices on Kubernetes"]}],
        projects=[], education=[], links={"github": "https://github.com/grace"},
    )
    session.add(profile)
    await session.flush()
    job = Job(user_id=user.id, source=JobSourceName.manual, origin=Origin.manual,
              dedupe_key="dk-honesty", company="Acme", title="Backend Engineer",
              role_title="Backend Engineer",
              description="Backend role using Go and Kubernetes.", track=Track.backend)
    session.add(job)
    await session.flush()
    return user, profile, job


@pytest.fixture
def real_mode(monkeypatch):
    """Real integrations off-the-fakes, with a LaTeX engine 'present' and R2 stubbed."""
    monkeypatch.setattr(settings, "use_fake_integrations", False)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tectonic")

    async def _put(key, data, content_type):
        return f"https://r2.example/{key}"

    monkeypatch.setattr(r2, "put_bytes", _put)


@pytest.mark.asyncio
async def test_real_mode_compile_failure_is_not_marked_ready(session, monkeypatch, real_mode):
    # The engine compiles via compile_tex → render.render_pdf_checked, so forcing that to fail makes
    # the engine's gate fail → needs_review; generation must not present it as ready.
    async def _fail(tex, *a, **k):
        return None, "! Undefined control sequence."

    async def _stub(tex):
        return b"%PDF-1.4 stub"

    monkeypatch.setattr(render, "render_pdf_checked", _fail)
    monkeypatch.setattr(render, "render_pdf", _stub)

    user, profile, job = await _seed(session)
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=user, emit=lambda *a, **k: None,
    )
    assert cv.status is CvStatus.failed              # never presented as ready
    assert job.status is not JobStatus.ready         # a fix-first state, not submittable
    assert cv.tailoring_diff["engine"]["state"] == "needs_review"


@pytest.mark.skipif(not has_compiler(), reason="needs tectonic for the engine to release")
@pytest.mark.asyncio
async def test_real_mode_clean_render_is_ready(session, real_mode):
    # A complete profile compiled for real by the engine releases → generation marks it ready.
    user, profile, job = await _seed(session)
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=user, emit=lambda *a, **k: None,
    )
    assert cv.status is CvStatus.ready               # the engine released the artifact
    assert job.status is JobStatus.ready
    assert cv.tailoring_diff["engine"]["state"] == "released"

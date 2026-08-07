"""Revamp run — parse a stored source CV and re-render it clean through the engine.

The uploaded text is the independent ledger, so grounding holds; the PATCH phase normalizes
the raw parsed dates (delta.fixed non-empty); the artifact route streams the clean PDF.
"""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.api.cv_runs import download_run_artifact, revamp_track_cv
from app.core.enums import PrincipalType, RunMode, Track
from app.cv_engine.render.compile import has_compiler
from app.cv_engine.runs.models import CvRun
from app.deps import Principal
from app.integrations import r2
from app.models.role_cv import RoleCv
from tests.helpers import seed_hunter

SOURCE_CV = """Ada Hunter
Backend Engineer
ada@example.com  |  linkedin.com/in/adahunter  |  github.com/adahunter

PROFESSIONAL SUMMARY
Backend engineer who builds production systems in Go and Kubernetes.

WORK EXPERIENCE
Senior Backend Engineer — Streamline
Jan 2020 - Present
- Built Go microservices serving many teams
- Reduced infra toil across the platform

SKILLS
Go, Kubernetes, Postgres, gRPC, Docker

EDUCATION
BSc Computer Science — University of Lagos
2013 - 2017
"""


def _principal(user) -> Principal:
    return Principal(id=user.id, type=PrincipalType.user, role="hunter", track_scope=[])


async def _store_source_cv(session, user) -> None:
    role_cv = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == Track.backend)
    )).scalar_one()
    key = f"{user.id}/role-cv/backend/source.txt"
    await r2.put_bytes(key, SOURCE_CV.encode("utf-8"), "text/plain")
    role_cv.source_file_key = key
    role_cv.original_filename = "cv.txt"
    await session.flush()


@pytest.mark.skipif(not has_compiler(), reason="needs tectonic to re-render a real artifact")
async def test_revamp_rebuilds_a_clean_cv(session):
    user, _ = await seed_hunter(session)
    await _store_source_cv(session, user)

    result = await revamp_track_cv(Track.backend, user, session)

    assert result["state"] == "released"
    assert result["artifact_ref"]
    assert result["parse"]["confidence"]["experience"] == 1.0
    # PATCH normalized the raw parsed dates → the delta shows the fix.
    assert result["delta"]["fixed"], "expected date/text fixes from the raw parse"
    assert "structure.date_format" in result["delta"]["resolved"]

    run = (await session.execute(
        select(CvRun).where(CvRun.id == UUID(result["run_id"]))
    )).scalar_one()
    assert run.mode is RunMode.revamp and run.job_id is None

    # The artifact route streams the clean PDF.
    resp = await download_run_artifact(UUID(result["run_id"]), _principal(user), session)
    assert resp.media_type == "application/pdf" and resp.body[:4] == b"%PDF"


async def test_revamp_requires_a_source_cv(session):
    user, _ = await seed_hunter(session)  # RoleCv exists but no stored R2 object
    from app.core.errors import DomainError, NotFoundError

    with pytest.raises((NotFoundError, DomainError)):
        await revamp_track_cv(Track.backend, user, session)

"""ATS checks persist as a durable, versioned `ats_analysis` row (not sessionStorage)."""

import pytest

from app.api import ats_checker
from app.core.enums import UserRole
from app.models.user import User
from app.repositories import ats_analysis as ats_repo
from app.security import hash_password

_JD = "Backend role. Kafka is required. Also Go, Kubernetes and Postgres."
_CV = "Backend engineer. Built Go microservices on Kubernetes with Postgres."


async def _seed_user(session):
    user = User(email="p@example.com", password_hash=hash_password("x"),
                name="Pat", role=UserRole.hunter)
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_check_persists_versioned_analysis(session):
    user = await _seed_user(session)

    result = await ats_checker._run_check(
        jd_text=_JD, cv_text=_CV, role_title="Backend Engineer",
        use_ai=True, cv_filename=None,
        session=session, user_id=user.id, job_id=None,
    )
    assert result["analysis_id"] is not None
    assert result["version"] == 1

    row = await ats_repo.latest(session, user_id=user.id, job_id=None)
    assert row is not None
    assert row.gate_status == "unevaluated"           # no artifact inspected → honest state
    assert "missing_critical" in row.breakdown        # the full breakdown is stored
    assert row.ai is not None and "recommendations" in row.ai

    # A second check appends a new version; latest() returns it.
    again = await ats_checker._run_check(
        jd_text=_JD, cv_text=_CV, role_title="Backend Engineer",
        use_ai=True, cv_filename=None,
        session=session, user_id=user.id, job_id=None,
    )
    assert again["version"] == 2
    newest = await ats_repo.latest(session, user_id=user.id, job_id=None)
    assert newest.version == 2


@pytest.mark.asyncio
async def test_check_without_session_does_not_persist(session):
    # The pure scoring path (no session/user) still works and simply doesn't record.
    user = await _seed_user(session)
    result = await ats_checker._run_check(
        jd_text=_JD, cv_text=_CV, role_title="Backend Engineer",
        use_ai=False, cv_filename=None,
    )
    assert result["analysis_id"] is None
    assert await ats_repo.latest(session, user_id=user.id, job_id=None) is None

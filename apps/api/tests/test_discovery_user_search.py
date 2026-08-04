"""Discovery is user-driven and token-safe.

- The provider query is scoped to the roles the user supplies, and off-title postings
  are dropped (so filtering the list is meaningful).
- With REAL integrations, a search with no role scope hits NO provider (zero API spend);
  fake mode has no token cost, so dev/tests keep discovering without a role.
"""

import pytest

from app.config import settings
from app.core.enums import Track, UserRole
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply import service
from app.security import hash_password


async def _seed(session, *, target_roles=None):
    user = User(email="h@example.com", password_hash=hash_password("x"),
                name="Hunter", role=UserRole.hunter)
    session.add(user)
    await session.flush()
    profile = MasterProfile(
        user_id=user.id, track=Track.backend, headline="Backend engineer",
        summary="I build backends.", skills=["Go", "Kubernetes"],
        experience=[], projects=[], education=[], links={},
        target_roles=target_roles or [],
    )
    session.add(profile)
    await session.flush()
    return user, profile


@pytest.mark.asyncio
async def test_search_roles_scope_and_filter(session):
    # The fake backend source yields "Backend Engineer (Go)" + "Platform Engineer".
    user, profile = await _seed(session, target_roles=[])
    new_jobs, _report = await service._run_sources(
        session, user_id=user.id, profile=profile,
        role_titles=["Backend Engineer"], cooldown=False,
    )
    titles = [j.title for j in new_jobs]
    assert any("Backend Engineer" in t for t in titles)      # on-title kept
    assert not any("Platform Engineer" in t for t in titles)  # off-title dropped


@pytest.mark.asyncio
async def test_no_roles_skips_every_source_in_real_mode(session, monkeypatch):
    # Real integrations + no search role + no target roles → skip all sources, zero fetches.
    monkeypatch.setattr(settings, "use_fake_integrations", False)
    user, profile = await _seed(session, target_roles=[])
    new_jobs, report = await service._run_sources(
        session, user_id=user.id, profile=profile, role_titles=[], cooldown=False,
    )
    assert new_jobs == []
    assert report and all(
        r["inserted"] == 0 and "skipped" in (r["note"] or "") for r in report
    )


@pytest.mark.asyncio
async def test_target_roles_used_when_no_search_role(session):
    # Beat path: no role_titles passed, but target_roles set → searches those (not skipped).
    user, profile = await _seed(session, target_roles=["Backend Engineer"])
    new_jobs, _report = await service._run_sources(
        session, user_id=user.id, profile=profile, cooldown=False,
    )
    assert any("Backend Engineer" in j.title for j in new_jobs)

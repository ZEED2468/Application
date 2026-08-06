"""Discovery is user-driven and token-safe.

- The provider query is scoped to the roles the user supplies, and off-title postings
  are dropped (so filtering the list is meaningful).
- With REAL integrations, a search with no role scope hits NO provider (zero API spend);
  fake mode has no token cost, so dev/tests keep discovering without a role.
"""

import pytest

from app.config import settings
from app.core.enums import JobSourceName, Track, UserRole
from app.llm.location_classify import is_appliable_from_nigeria
from app.llm.track_classify import classify_rules
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply import service
from app.pipelines.apply.service import _decide_track
from app.security import hash_password
from app.sources.base import RawJob


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


# --- Track assignment (the "frontend search stored as general" fix) ---


def test_neutral_job_keeps_searched_track():
    # A JD with no signal words classifies "general" — but discovered under a frontend
    # search it must be tagged frontend, not silently mislabeled general.
    track, drop = _decide_track(
        title="Software Engineer", description="Join our growing team.",
        profile_track=Track.frontend, selected_tracks=None,
    )
    assert track is Track.frontend and drop is False


def test_neutral_job_general_only_without_context():
    track, drop = _decide_track(
        title="Software Engineer", description="Join our growing team.",
        profile_track=Track.general, selected_tracks=None,
    )
    assert track is Track.general and drop is False


def test_confident_offtarget_is_dropped_under_track_filter():
    # Clearly a backend job, but the user searched only frontend → off-target drop.
    track, drop = _decide_track(
        title="Backend Engineer", description="Go microservices, Kubernetes, Postgres.",
        profile_track=Track.frontend, selected_tracks=["frontend"],
    )
    assert drop is True


def test_uncertain_job_kept_and_tagged_selected_track():
    # Neutral JD under a frontend-only search → kept, tagged frontend (not dropped).
    track, drop = _decide_track(
        title="Software Engineer", description="Great team.",
        profile_track=Track.frontend, selected_tracks=["frontend"],
    )
    assert track is Track.frontend and drop is False


def test_literal_track_name_in_title_wins():
    track, _drop = _decide_track(
        title="Frontend Developer", description="whatever",
        profile_track=Track.backend, selected_tracks=["frontend", "backend"],
    )
    assert track is Track.frontend


def test_broadened_signals_classify_web_role_as_frontend():
    # Previously scored 0 signals → general; now frontend.
    assert classify_rules(
        title="Web Developer",
        description="Build web apps with JavaScript, HTML and CSS.",
    ) is Track.frontend


@pytest.mark.asyncio
async def test_frontend_discovery_stores_frontend_track(session):
    # End-to-end: run discovery under a frontend profile; every stored job is frontend.
    user, profile = await _seed(session, target_roles=[])
    profile.track = Track.frontend
    await session.flush()
    new_jobs, _report = await service._run_sources(
        session, user_id=user.id, profile=profile,
        role_titles=["Frontend Engineer"], cooldown=False,
    )
    assert new_jobs, "fake frontend source should yield at least one job"
    assert all(j.track is Track.frontend for j in new_jobs)


# --- Nigeria eligibility gate ---


def test_nigeria_eligibility_keep_drop_matrix():
    keep = [
        ("Frontend Engineer", "Remote", ""),
        ("Engineer", "Remote (worldwide)", ""),
        ("Backend Engineer", "Lagos, Nigeria", ""),
        ("Engineer", "Remote - Africa", ""),
        ("Engineer", "", "Great team, generic description"),  # ambiguous → keep
    ]
    drop = [
        ("Engineer", "New York, NY", "onsite role"),
        ("Engineer", "London, UK", ""),
        ("Engineer", "Berlin (hybrid)", ""),
        ("Engineer", "Remote", "Remote (US only)"),
        ("Engineer", "Remote", "You must be authorized to work in the UK"),
        ("Engineer", "Remote", "US citizens only"),
    ]
    for t, l, d in keep:
        assert is_appliable_from_nigeria(title=t, location=l, description=d), (l, d)
    for t, l, d in drop:
        assert not is_appliable_from_nigeria(title=t, location=l, description=d), (l, d)


def _stub_two_jobs(monkeypatch):
    """Monkeypatch discovery to yield one Nigeria-appliable job + one onsite-US job."""
    remote = RawJob(
        source=JobSourceName.greenhouse, source_job_id="ok", company="RemoteCo",
        title="Backend Engineer", location="Remote - Africa", url="https://x/1",
        description="Go microservices, remote across Africa.",
    )
    onsite_us = RawJob(
        source=JobSourceName.greenhouse, source_job_id="no", company="USCo",
        title="Backend Engineer", location="New York, NY", url="https://x/2",
        description="Onsite in NYC. US citizens only.",
    )

    class _Stub:
        name = JobSourceName.greenhouse

        def supports(self, track):
            return True

        async def fetch(self, query):
            yield remote
            yield onsite_us

    monkeypatch.setattr(service, "active_sources", lambda: [_Stub()])


@pytest.mark.asyncio
async def test_discovery_drops_ineligible_jobs(session, monkeypatch):
    _stub_two_jobs(monkeypatch)
    user, profile = await _seed(session, target_roles=["Backend Engineer"])
    kept, _report = await service._run_sources(
        session, user_id=user.id, profile=profile,
        role_titles=["Backend Engineer"], cooldown=False,  # nigeria_only defaults True
    )
    assert {j.company for j in kept} == {"RemoteCo"}  # onsite-US dropped


@pytest.mark.asyncio
async def test_discovery_keeps_ineligible_when_gate_off(session, monkeypatch):
    _stub_two_jobs(monkeypatch)
    user, profile = await _seed(session, target_roles=["Backend Engineer"])
    kept, _report = await service._run_sources(
        session, user_id=user.id, profile=profile,
        role_titles=["Backend Engineer"], cooldown=False, nigeria_only=False,
    )
    assert {j.company for j in kept} == {"RemoteCo", "USCo"}  # gate off → both kept


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

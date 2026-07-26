"""Expanded truth corpus (R4) + track-centric fields (R3).

Verified extras + preferred skills join the allowed truth corpus (so tailoring can
surface them) and drive the ATS "underutilized verified" signal; the per-track
preference + active-track setters round-trip.
"""

from __future__ import annotations

import pytest

from app.api.onboarding import (
    ActiveTrackBody,
    PreferencesBody,
    VerifiedExtrasBody,
    set_active_track,
    set_preferences,
    set_verified_extras,
)
from app.core.enums import Track
from app.models.master_profile import MasterProfile
from app.pipelines.apply import intel
from app.pipelines.apply.cv_parse import cv_json_from_text
from app.repositories import profiles as profiles_repo
from tests.helpers import seed_hunter


def test_profile_to_dict_surfaces_verified_extras_into_allowed_skills():
    p = MasterProfile(
        user_id=None, track=Track.backend, skills=["Go"],
        verified_extras={"frameworks": ["FastAPI"], "tools": ["Docker"]},
        preferred_skills=["Kafka"], experience=[], projects=[], education=[], links={},
    )
    d = profiles_repo.profile_to_dict(p)
    assert {"FastAPI", "Docker", "Kafka"} <= set(d["skills"])  # allowed fact set widened
    assert d["verified_extras"]["frameworks"] == ["FastAPI"]


def test_verified_terms_drive_underutilized_signal():
    cv = cv_json_from_text("Skills: Go")
    jd = "Requirements: Go, Docker, Kubernetes."
    t = intel.tool_analysis(jd_text=jd, cv_json=cv, verified_terms=["Docker"])
    under = {x.lower() for x in t["underutilized_verified"]}
    assert "docker" in under  # verified + wanted by JD + absent from CV


@pytest.mark.asyncio
async def test_verified_extras_and_preferences_roundtrip(session):
    user, profile = await seed_hunter(session)
    await set_verified_extras(
        Track.backend,
        VerifiedExtrasBody(extras={"frameworks": ["FastAPI", "FastAPI", ""], "bad": "notlist"}),
        user=user, session=session,
    )
    await session.refresh(profile)
    assert profile.verified_extras == {"frameworks": ["FastAPI"]}  # dedup, drop empty + non-list

    await set_preferences(
        Track.backend,
        PreferencesBody(preferred_skills=["Kafka", "Kafka"], career_preferences={"remote": True}),
        user=user, session=session,
    )
    await session.refresh(profile)
    assert profile.preferred_skills == ["Kafka"] and profile.career_preferences == {"remote": True}


@pytest.mark.asyncio
async def test_active_track_roundtrip(session):
    user, _ = await seed_hunter(session)
    r = await set_active_track(ActiveTrackBody(track=Track.frontend), user=user, session=session)
    assert r["active_track"] == "frontend"
    assert user.active_track is Track.frontend

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
from app.pipelines.apply import intel, render
from app.pipelines.apply.cv_parse import cv_json_from_text
from app.pipelines.generation import enrich_from_verified_extras
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


def test_promoted_extras_become_sections_not_flat_skills():
    """Certifications / languages / project-like extras surface as their own CV
    sections (deeper CV), and are NOT also dumped into the flat skills list."""
    p = MasterProfile(
        user_id=None, track=Track.backend, skills=["Go"],
        verified_extras={
            "tools": ["Docker"],                       # skill-like -> stays in skills
            "certifications": ["AWS SA", "CKA"],       # promoted -> own section
            "languages": ["English", "Yoruba"],        # promoted -> own section
            "side_projects": ["jobhunter.dev"],        # promoted -> Projects
            "open_source": ["contrib to FastAPI"],     # promoted -> Projects
        },
        preferred_skills=[], experience=[], projects=[{"name": "Existing"}],
        education=[], links={},
    )
    d = profiles_repo.profile_to_dict(p)
    # Skill-like extras widen skills; promoted ones do NOT (no duplication with sections).
    assert "Docker" in d["skills"]
    assert not ({"AWS SA", "CKA", "English", "Yoruba", "jobhunter.dev"} & set(d["skills"]))

    cv = enrich_from_verified_extras(
        {"headline": "Backend Engineer", "skills": d["skills"], "projects": [{"name": "Existing"}]},
        d,
    )
    assert cv["certifications"] == ["AWS SA", "CKA"]
    assert cv["languages"] == ["English", "Yoruba"]
    names = [pr.get("name") for pr in cv["projects"]]
    assert names == ["Existing", "contrib to FastAPI", "jobhunter.dev"]  # merged, order-stable, deduped

    tex = render.build_tex(cv, name="Ada Lovelace")
    for marker in ("Certifications", "AWS SA", "Languages", "Yoruba", "jobhunter.dev"):
        assert marker in tex  # every rendered extra traces to the profile (truth-bounded)


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

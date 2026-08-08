"""Guided onboarding status (R2) + Career Workspace details (R8)."""

from __future__ import annotations

import pytest

from app.api.onboarding import (
    CareerDetailsBody,
    onboarding_status,
    set_career_details,
)
from app.models.user_llm_credential import UserLlmCredential
from tests.helpers import seed_hunter


@pytest.mark.asyncio
async def test_onboarding_status_reports_next_action(session):
    user, profile = await seed_hunter(session)  # a set-up hunter already has a parsed CV

    r = await onboarding_status(user=user, session=session)
    assert r["complete"] is False
    # The CV is uploaded (seed_hunter); the next required action is confirming the profile.
    assert r["next_action"]["key"] == "confirm"

    profile.confirmed = True
    profile.target_roles = ["Backend Engineer"]
    session.add(UserLlmCredential(user_id=user.id, provider="openai", encrypted_api_key="x"))
    await session.flush()

    r2 = await onboarding_status(user=user, session=session)
    assert r2["complete"] is True and r2["next_action"] is None
    assert all(s["done"] for s in r2["steps"])


@pytest.mark.asyncio
async def test_career_details_roundtrip(session):
    user, profile = await seed_hunter(session)
    await set_career_details(
        profile.track,
        CareerDetailsBody(
            links={"linkedin": "https://linkedin.com/in/x"},
            preferred_locations=["Remote", "Remote", ""],
            preferred_job_types=["Full-time"],
            salary_expectation={"min": 80000, "currency": "USD"},
        ),
        user=user, session=session,
    )
    await session.refresh(profile)
    assert profile.links == {"linkedin": "https://linkedin.com/in/x"}
    assert profile.preferred_locations == ["Remote"]  # deduped, empty dropped
    assert profile.preferred_job_types == ["Full-time"]
    assert profile.salary_expectation == {"min": 80000, "currency": "USD"}

"""A present-but-invalid provider key (or a provider outage) must not crash CV
generation — the hook + cover-letter LLM calls fall back to their deterministic,
truth-bounded builders, exactly like tailoring already does."""

from __future__ import annotations

import pytest

from app.core.enums import Track
from app.llm import client as llm_client
from app.llm import cover_letter, hookfinder
from app.llm.hookfinder import Hook


async def _boom(*_a, **_k):
    raise RuntimeError("Error code: 401 - invalid x-api-key")


@pytest.mark.asyncio
async def test_hookfinder_falls_back_when_live_call_raises(monkeypatch):
    # is_live() only checks key *presence*, so an invalid key gets here and raises.
    monkeypatch.setattr(llm_client, "is_live", lambda feature: True)
    monkeypatch.setattr(llm_client, "complete_text", _boom)

    hook = await hookfinder.find_hook(
        company="Acme", track=Track.backend, job_description="We build payment APIs."
    )
    assert isinstance(hook, Hook)
    assert hook.text  # deterministic hook, no exception


@pytest.mark.asyncio
async def test_cover_letter_falls_back_when_live_call_raises(monkeypatch):
    monkeypatch.setattr(llm_client, "is_live", lambda feature: True)
    monkeypatch.setattr(llm_client, "complete_text", _boom)

    body = await cover_letter.generate_cover_letter(
        candidate_name="Alan Turing",
        company="Acme",
        role_title="Backend Engineer",
        track=Track.backend,
        hook=Hook(text="your payments API work", source="job_description"),
        profile={"experience": [{"bullets": ["Built a payments API at scale"]}]},
        jd_text="Backend APIs in Go.",
    )
    assert isinstance(body, str)
    assert "Alan Turing" in body  # deterministic 3-paragraph builder ran

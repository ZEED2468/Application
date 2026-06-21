"""Relevance prefilter, track classification, and the tailoring truth boundary."""

import pytest

from app.core.enums import Track
from app.llm import relevance, tailoring, track_classify


def test_relevance_scores_overlap():
    high = relevance.score(
        title="Backend Engineer (Go)",
        description="Build Go microservices and distributed systems",
        skills=["Go", "microservices", "distributed systems"],
    )
    low = relevance.score(
        title="Pastry Chef", description="Bake croissants", skills=["Go", "Kubernetes"]
    )
    assert high > low
    assert relevance.passes(high)
    assert not relevance.passes(low)


def test_track_classification():
    assert track_classify.classify(
        title="Senior React Native Engineer", description="mobile UI animation"
    ) is Track.frontend
    assert track_classify.classify(
        title="Backend Engineer", description="Go microservices kubernetes"
    ) is Track.backend


def test_tailoring_is_truth_bounded():
    profile = {
        "headline": "Backend engineer",
        "summary": "I build production backend systems.",
        "skills": ["Go", "NestJS", "Kubernetes", "React"],
        "experience": [
            {"title": "Backend Engineer", "company": "Streamline",
             "bullets": ["Built Go microservices", "Ran Kubernetes clusters"]},
            {"title": "Frontend Intern", "company": "Pixel",
             "bullets": ["Built React components"]},
        ],
        "projects": [{"name": "Distributed Queue", "description": "A Go task queue"}],
        "education": [], "links": {},
    }
    cv, diff = tailoring.tailor_fake(
        profile, job_title="Go Backend Engineer",
        job_description="Go microservices, distributed systems, Kubernetes",
    )
    # Provably no fabrication.
    tailoring.assert_truth_bounded(profile, cv)
    # Backend experience ranked ahead of the frontend one.
    assert cv["experience"][0]["company"] == "Streamline"
    assert "Go" in diff["skills_emphasized"]


def test_truth_guard_rejects_fabrication():
    profile = {"skills": ["Go"], "experience": [], "projects": []}
    fabricated = {"skills": ["Go", "Rust"]}  # Rust not in profile
    with pytest.raises(ValueError):
        tailoring.assert_truth_bounded(profile, fabricated)


@pytest.mark.asyncio
async def test_tailor_threads_priority_techs_and_stays_bounded():
    profile = {
        "headline": "Backend engineer", "summary": "I build backend systems.",
        "skills": ["Go", "Kubernetes"],
        "experience": [{"title": "Backend Engineer", "company": "Streamline",
                        "bullets": ["Built Go microservices"]}],
        "projects": [], "education": [], "links": {},
    }
    # Fake mode (default in tests): deterministic + provably truth-bounded, and the
    # requested priority techs are recorded for the live reframe.
    cv, diff = await tailoring.tailor(
        profile, job_title="Go Backend Engineer", job_description="Go microservices",
        priority_techs=["Kafka"],
    )
    tailoring.assert_truth_bounded(profile, cv)
    assert diff["priority_techs"] == ["Kafka"]


@pytest.mark.asyncio
async def test_tailor_parses_fenced_json(monkeypatch):
    from app.llm import client

    monkeypatch.setattr(client, "is_live", lambda feature=None: True)
    payload = (
        '```json\n{"headline":"H","summary":"S","skills":["Go"],'
        '"experience":[],"projects":[],"education":[],"links":{}}\n```'
    )

    async def _ok(*a, **k):
        return payload

    monkeypatch.setattr(client, "complete_text", _ok)
    cv, diff = await tailoring.tailor(
        {"skills": ["Go"]}, job_title="Backend", job_description="Go"
    )
    assert cv["headline"] == "H" and diff["strategy"] == "llm"


@pytest.mark.asyncio
async def test_tailor_falls_back_on_live_failure(monkeypatch):
    """A non-JSON model reply or API error must never 500 — fall back to the
    deterministic, truth-bounded path."""
    from app.llm import client

    monkeypatch.setattr(client, "is_live", lambda feature=None: True)

    async def _bad(*a, **k):
        return "Sure! Here's the CV:\n```json\n{ not valid json"

    monkeypatch.setattr(client, "complete_text", _bad)
    profile = {
        "headline": "h", "summary": "s", "skills": ["Go"],
        "experience": [{"bullets": ["Built Go services"]}],
        "projects": [], "education": [], "links": {},
    }
    cv, diff = await tailoring.tailor(profile, job_title="Backend", job_description="Go")
    tailoring.assert_truth_bounded(profile, cv)
    assert diff.get("fell_back") == "llm_failed"

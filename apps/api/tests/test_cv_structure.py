"""CV structuring and AI track classification."""

import pytest

from app.core.enums import Track
from app.llm import cv_structure, track_classify

SAMPLE_CV = """
Jane Developer
Backend Engineer

SUMMARY
Built APIs with Node.js, PostgreSQL, and Kubernetes.

EXPERIENCE
Acme Corp — Software Engineer
- Built REST APIs in Node.js
- Deployed services on Kubernetes

SKILLS
Node.js, PostgreSQL, Kubernetes, TypeScript
"""


def test_structure_offline_extracts_lines():
    result = cv_structure.structure_offline(SAMPLE_CV, track="backend")
    assert result.structured_by == "offline"
    assert result.headline
    assert len(result.skills) > 0
    assert len(result.experience) == 1
    assert len(result.experience[0]["bullets"]) > 2


def test_truth_bounded_rejects_fabrication():
    assert cv_structure._truth_bounded(
        SAMPLE_CV,
        {"skills": ["Node.js"], "experience": [{"bullets": ["Built REST APIs in Node.js"]}]},
    )
    assert not cv_structure._truth_bounded(
        SAMPLE_CV,
        {"skills": ["COBOL"]},
    )


def test_classify_rules_unchanged():
    assert track_classify.classify(
        title="Senior React Native Engineer", description="mobile UI animation"
    ) is Track.frontend


@pytest.mark.asyncio
async def test_classify_best_single_upload():
    match = await track_classify.classify_best(
        title="Backend Engineer",
        description="Node.js APIs and PostgreSQL",
        available={Track.backend: "Node.js Kubernetes PostgreSQL backend APIs"},
    )
    assert match.track is Track.backend
    assert match.method == "availability"


@pytest.mark.asyncio
async def test_classify_best_fallback_when_jd_track_missing():
    match = await track_classify.classify_best(
        title="Backend Engineer",
        description="Node.js microservices",
        available={Track.general: "full-stack Next.js Python product engineer"},
    )
    assert match.track is Track.general
    assert "backend" in match.reason.lower() or "general" in match.reason.lower()


@pytest.mark.asyncio
async def test_classify_best_falls_back_when_llm_fails(monkeypatch):
    async def _fail(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.llm.client.try_complete_text", _fail)
    match = await track_classify.classify_best(
        title="Senior React Engineer",
        description="React TypeScript frontend UI",
        available={
            Track.frontend: "React TypeScript CSS frontend mobile",
            Track.backend: "Go Kubernetes PostgreSQL APIs",
        },
    )
    assert match.track is Track.frontend
    assert match.method == "rules"

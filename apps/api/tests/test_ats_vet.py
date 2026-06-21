"""AI gap vetting."""

import json

import pytest

from app.llm import ats_vet
from app.pipelines.apply import ats
from app.pipelines.manual import service
from tests.helpers import EventSink, seed_hunter


def _sample_profile() -> dict:
    return {
        "skills": ["JavaScript", "TypeScript", "NestJS", "Express", "MongoDB", "PostgreSQL", "Linux"],
        "experience": [
            {"bullets": ["Node.js backend with MongoDB", "OAuth2 JWT security", "RESTful APIs"]},
        ],
        "summary": "Backend engineer",
        "education": [{"details": "OOP, database systems"}],
        "projects": [],
    }


def _sample_jd() -> str:
    return (
        "Backend Engineer. Node.js, Java, MySQL, Azure, Git, Jest, TypeScript, NestJS. "
        "Good understanding of skills in a collaborative environment."
    )


def test_vet_gaps_offline_drops_profile_evidence():
    profile = _sample_profile()
    jd = _sample_jd()
    breakdown = ats.score(
        cv_json={
            "skills": profile["skills"],
            "experience": profile["experience"],
            "summary": profile["summary"],
            "education": profile["education"],
        },
        jd_text=jd,
        role_title="Backend Engineer",
    )
    candidates = ats.gap_skills(breakdown, limit=10)
    result = ats_vet.vet_gaps_offline(
        profile=profile,
        jd_text=jd,
        candidate_gaps=candidates,
        missing_keywords=breakdown["missing_keywords"],
    )
    gap_skills = {g.skill.lower() for g in result.gaps}
    assert "good" not in gap_skills
    assert "understanding" not in gap_skills
    assert "javascript" not in gap_skills


def test_parse_vet_response_validates_skills():
    jd = _sample_jd()
    profile = _sample_profile()
    raw = json.dumps(
        {
            "gaps": [
                {
                    "skill": "Java",
                    "reason": "JD requires Java; profile has JS/TS only.",
                    "question": 'Does the hunter have genuine "Java" experience?',
                },
                {
                    "skill": "Blockchain",
                    "reason": "Invented",
                    "question": 'Does the hunter have "Blockchain" experience?',
                },
            ],
            "removed": ["good", "understanding"],
            "notes": "Filtered noise.",
        }
    )
    result = ats_vet._parse_vet_response(
        raw,
        jd_text=jd,
        candidate_gaps=["java", "git"],
        missing_keywords=["java", "git", "azure"],
        profile=profile,
        limit=5,
    )
    assert len(result.gaps) == 1
    assert result.gaps[0].skill == "Java"
    assert "Blockchain" not in [g.skill for g in result.gaps]


@pytest.mark.asyncio
async def test_manual_vet_gaps_replaces_unresolved_prompts(session):
    user, _ = await seed_hunter(session)
    jd = """Backend Engineer at Example Corp
    Node.js, Java, Git, Jest required. Good understanding of teamwork."""
    chat, prompts = await service.start_session(
        session, user_id=user.id, jd_text=jd, emit=EventSink()
    )
    assert len(prompts) >= 1
    old_unresolved = [p for p in prompts if not p.resolved]

    new_prompts = await service.vet_gaps_with_ai(session, chat=chat, emit=EventSink())
    assert chat.ats_breakdown.get("ai_vetted") is True
    assert all(
        "good" not in p.question.lower() and "understanding" not in p.question.lower()
        for p in new_prompts
        if not p.resolved
    )
    assert len(new_prompts) <= len(old_unresolved) + 1

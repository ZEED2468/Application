"""Global ATS checker API."""

import pytest

from app.api.ats_checker import _load_profile_cv, _profile_sources, _run_check
from app.core.enums import ParseStatus, Track
from app.models.cover_letter import CoverLetterTemplate
from app.models.role_cv import RoleCv
from app.pipelines.apply.cv_parse import cv_json_from_text
from app.pipelines.apply import ats
from tests.helpers import seed_hunter


SAMPLE_JD = """
Senior Backend Engineer
Requirements: Go, Kubernetes, PostgreSQL, REST APIs, microservices.
Good understanding of teamwork in a fast-paced environment.
"""

SAMPLE_CV = """
Jane Developer — Backend Engineer
Skills: Go, Kubernetes, PostgreSQL, Docker, gRPC, REST APIs
Experience:
- Built Go microservices on Kubernetes serving 10k RPS
- Designed PostgreSQL schemas and query optimization
"""


async def _seed_parsed_role_cv(session, user, profile, *, filename="backend.pdf"):
    session.add(
        RoleCv(
            user_id=user.id,
            track=profile.track,
            original_filename=filename,
            parse_status=ParseStatus.parsed,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_ats_check_run():
    result = await _run_check(
        jd_text=SAMPLE_JD,
        cv_text=SAMPLE_CV,
        role_title="Backend Engineer",
        use_ai=False,
        cv_filename=None,
    )
    assert result["rule_based"]["score"] >= 0
    matched = [k.lower() for k in result["rule_based"]["breakdown"]["matched_keywords"]]
    assert "go" in matched or "kubernetes" in matched
    assert "good" not in result["rule_based"]["gaps"]
    assert result["ai"] is None


@pytest.mark.asyncio
async def test_ats_check_with_offline_ai():
    result = await _run_check(
        jd_text=SAMPLE_JD,
        cv_text=SAMPLE_CV,
        role_title="Backend Engineer",
        use_ai=True,
        cv_filename="resume.pdf",
    )
    assert result["ai"] is not None
    assert result["cv_filename"] == "resume.pdf"
    assert result["ai"]["verdict"]


@pytest.mark.asyncio
async def test_profile_sources_lists_parsed_tracks(session):
    user, profile = await seed_hunter(session)
    await _seed_parsed_role_cv(session, user, profile)

    tracks = await _profile_sources(session, user_id=user.id)
    assert len(tracks) == 1
    assert tracks[0]["track"] == "backend"
    assert tracks[0]["filename"] == "backend.pdf"
    assert tracks[0]["word_count"] > 0


@pytest.mark.asyncio
async def test_load_profile_cv(session):
    user, profile = await seed_hunter(session)
    await _seed_parsed_role_cv(session, user, profile, filename="go-resume.pdf")

    text, filename, source = await _load_profile_cv(
        session, user_id=user.id, track=Track.backend,
    )
    assert source == "profile"
    assert filename == "go-resume.pdf"
    assert "go" in text.lower()


@pytest.mark.asyncio
async def test_run_check_includes_cover_letter_template(session):
    user, _ = await seed_hunter(session)
    session.add(
        CoverLetterTemplate(
            user_id=user.id,
            body="Dear {company}, I am excited about {role}.",
            original_filename="template.docx",
            name="Default",
        )
    )
    await session.flush()

    tpl = {
        "body": "Dear {company}, I am excited about {role}.",
        "filename": "template.docx",
        "name": "Default",
    }
    result = await _run_check(
        jd_text=SAMPLE_JD,
        cv_text=SAMPLE_CV,
        role_title="Backend Engineer",
        use_ai=False,
        cv_filename="resume.pdf",
        track=Track.backend,
        cv_source="profile",
        cover_letter_template=tpl,
    )
    assert result["track"] == "backend"
    assert result["cv_source"] == "profile"
    assert result["cover_letter_template"]["filename"] == "template.docx"


def test_cv_json_from_text_scores():
    cv = cv_json_from_text(SAMPLE_CV)
    breakdown = ats.score(cv_json=cv, jd_text=SAMPLE_JD, role_title="Backend Engineer")
    assert breakdown["score"] > 0

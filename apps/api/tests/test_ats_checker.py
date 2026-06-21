"""Global ATS checker API."""

import pytest

from app.api.ats_checker import _run_check
from app.pipelines.apply.cv_parse import cv_json_from_text
from app.pipelines.apply import ats


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


def test_cv_json_from_text_scores():
    cv = cv_json_from_text(SAMPLE_CV)
    breakdown = ats.score(cv_json=cv, jd_text=SAMPLE_JD, role_title="Backend Engineer")
    assert breakdown["score"] > 0

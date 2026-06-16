"""Internal ATS scorer + cover-letter truth boundary."""

from app.core.enums import Track
from app.llm import cover_letter
from app.llm.hookfinder import Hook
from app.pipelines.apply import ats


def test_ats_scores_and_breakdown():
    cv_json = {
        "skills": ["Go", "Kubernetes", "microservices", "Postgres"],
        "experience": [{"bullets": ["Built Go microservices on Kubernetes"]}],
    }
    jd = "We want a backend engineer with Go, Kubernetes, microservices and Postgres."
    result = ats.score(cv_json=cv_json, jd_text=jd, role_title="Backend Engineer")
    assert 0 <= result["score"] <= 100
    assert "go" in [m.lower() for m in result["matched_keywords"]]
    assert result["format_flags"]["single_column"] is True
    assert "internal ATS match" in result["framing"]


def test_ats_surfaces_missing_as_gaps():
    cv_json = {"skills": ["Go"]}
    jd = "Looking for Rust, Kafka and Terraform experience."
    result = ats.score(cv_json=cv_json, jd_text=jd, role_title="Engineer")
    gaps = ats.gap_skills(result)
    assert any(g in ("rust", "kafka", "terraform") for g in gaps)


def test_cover_letter_is_three_paragraphs_and_truthful():
    profile = {
        "summary": "I build backend systems.",
        "experience": [{"bullets": ["Built a distributed Go task queue"]}],
        "projects": [{"description": "An event-driven pipeline"}],
        "skills": ["Go"],
    }
    body = cover_letter.build_three_paragraphs(
        candidate_name="Ada Lovelace", company="Acme", role_title="Backend Engineer",
        hook=Hook(text="your recent event-driven platform launch", source="blog"),
        profile=profile, jd_text="Go distributed systems",
    )
    paras = [p for p in body.split("\n\n") if p.strip()]
    assert len(paras) == 3  # exactly three paragraphs
    # Mirrored work is a REAL accomplishment drawn from the profile.
    assert "distributed Go task queue" in body or "event-driven pipeline" in body
    assert "Acme" in body and "Ada Lovelace" in body

"""The consolidated ATS scorer: gate -> cap -> score, one honest number out.

Covers the settled decisions in the Product Evolution Constitution §10.2:
- missing emphasis-marked must-haves cap the ceiling (not a linear subtraction);
- supporting coverage saturates (no reward for keyword-stuffing);
- AI false-positives are retracted BEFORE the number is computed;
- title/seniority alignment is excluded from the number and surfaced as a stretch signal;
- absence of an artifact is `unevaluated`, never a fabricated pass; a failed gate = no number.
"""

from app.pipelines.apply import ats
from app.pipelines.apply.latex_regen import _cv_prompt


def test_missing_critical_caps_the_ceiling():
    jd = "Backend role. Kafka is required. Also Postgres and Redis."  # Kafka = must-have
    have = {"skills": ["Kafka", "Postgres", "Redis"]}
    missing = {"skills": ["Postgres", "Redis"]}  # strong supporting, but no Kafka
    full = ats.score(cv_json=have, jd_text=jd)
    capped = ats.score(cv_json=missing, jd_text=jd)
    assert "kafka" in [k.lower() for k in capped["missing_critical"]]
    # Missing the must-have caps well below the fully-covered CV even though supporting
    # coverage is high — "missing a must-have is not an 80, it is not ready."
    assert capped["score"] < full["score"]
    assert capped["score"] <= 100 * capped["criticals_coverage"] + 0.01


def test_false_positives_are_retracted_before_scoring():
    jd = "Requirements: Go, Kubernetes, Blockchain."
    cv = {"skills": ["Go", "Kubernetes"]}
    base = ats.score(cv_json=cv, jd_text=jd)
    corrected = ats.score(cv_json=cv, jd_text=jd, false_positives=["Blockchain"])
    assert "blockchain" not in [k.lower() for k in corrected["missing_keywords"]]
    assert corrected["score"] >= base["score"]  # retracting a bogus gap can only help


def test_title_alignment_excluded_from_score_and_surfaced_as_stretch():
    jd = "Requirements: Go, Postgres."
    cv = {"skills": ["Go", "Postgres"]}
    aligned = ats.score(cv_json=cv, jd_text=jd, role_title="Go Engineer")
    stretch = ats.score(cv_json=cv, jd_text=jd, role_title="Principal Rust Architect")
    # Identical content coverage → identical document score, regardless of title fit …
    assert aligned["score"] == stretch["score"]
    # … and the mismatch shows up as a stretch signal, not inside the number.
    assert stretch["stretch"]["is_stretch"] is True
    assert aligned["stretch"]["is_stretch"] is False


def test_failed_gate_yields_no_number():
    r = ats.score(cv_json={"skills": ["Go"]}, jd_text="Requirements: Go.",
                  gate={"status": "fail", "reason": "two-column"})
    assert r["score"] is None          # a fix-first state, never a fabricated number
    assert r["gate"]["status"] == "fail"


def test_no_artifact_is_unevaluated_not_a_pass():
    r = ats.score(cv_json={"skills": ["Go"]}, jd_text="Requirements: Go.")
    assert r["gate"]["status"] == "unevaluated"
    assert r["score"] is not None      # content readiness is still shown, honestly flagged


def test_supporting_coverage_saturates():
    # concave: 0.0->0.5 gains strictly more than 0.5->1.0 (diminishing returns).
    assert ats._saturate(0.5) - ats._saturate(0.0) > ats._saturate(1.0) - ats._saturate(0.5)


def test_regen_prompt_carries_recommendations_canonical_and_legacy():
    canonical = _cv_prompt(template_tex="X", cv_json={}, owner_name="A", job_title="R",
                           priority_techs=[], ats_recs={"recommendations": ["USE_CANON"]})
    legacy = _cv_prompt(template_tex="X", cv_json={}, owner_name="A", job_title="R",
                        priority_techs=[], ats_recs={"ai_recommendations": ["USE_LEGACY"]})
    assert "USE_CANON" in canonical    # canonical key reaches the rewrite prompt
    assert "USE_LEGACY" in legacy      # legacy key still honored (no silent drop)

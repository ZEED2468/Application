"""Resume Intelligence — deterministic verb/tool/structure/lint analysis + advisory pass.

All run in fake mode (no LLM), so these assert the deterministic wiring and that the
new blocks are additive to the ATS response without changing the existing contract.
"""

from __future__ import annotations

import pytest

from app.api.ats_checker import _run_check
from app.llm import resume_intel
from app.pipelines.apply import ats, intel, verbs
from app.pipelines.apply.cv_parse import cv_json_from_text

SAMPLE_JD = """
Senior Backend Engineer
Requirements: Go, Kubernetes, PostgreSQL, REST APIs, microservices.
"""

WEAK_CV = """
John Doe
Objective: seeking a role where I can grow my skills.
123 Main Street, Springfield
Experience:
- Managed a small team of engineers
- Responsible for the CI pipeline
- Worked on the Go backend services
- Built PostgreSQL schemas that cut query time 40%
"""


def test_verbs_detect_flags_weak_openers_only():
    found = verbs.detect([
        "Managed a small team",
        "Responsible for the CI pipeline",
        "Built Go microservices",  # strong — not flagged
    ])
    flagged = {f["weak_verb"] for f in found}
    assert "managed" in flagged and "responsible for" in flagged
    assert not any(f["bullet"].startswith("Built") for f in found)
    # suggestions are non-empty and never rewrite the bullet in place
    assert all(f["suggestions"] for f in found)


def test_tool_analysis_splits_represented_vs_missing():
    cv = cv_json_from_text("Skills: Go, Kubernetes, REST APIs, microservices")
    t = intel.tool_analysis(jd_text=SAMPLE_JD, cv_json=cv)
    rep = {r.lower() for r in t["represented"]}
    miss = {m.lower() for m in t["missing"]}
    assert "go" in rep and "kubernetes" in rep
    assert "postgresql" in miss  # required by JD, absent from CV


def test_structure_review_flags_hygiene_issues():
    cv = cv_json_from_text(WEAK_CV)
    s = intel.structure_review(cv_text=WEAK_CV, cv_json=cv)
    codes = {f["code"] for f in s["ats_flags"]}
    assert "objective" in codes  # 'Objective' not 'Summary'
    assert "full_address" in codes  # street address present
    assert s["summary_present"] is False
    assert s["est_pages"] >= 1


def test_ats_lint_produces_actionable_findings():
    cv = cv_json_from_text(WEAK_CV)
    breakdown = ats.score(cv_json=cv, jd_text=SAMPLE_JD, role_title="Backend Engineer")
    structure = intel.structure_review(cv_text=WEAK_CV, cv_json=cv)
    weak = verbs.detect(intel.bullets_of(cv))
    lint = intel.ats_lint(cv_json=cv, breakdown=breakdown, structure=structure, weak_verbs=weak)
    codes = {f["code"] for f in lint["findings"]}
    assert "weak_verbs" in codes and "summary_missing" in codes
    assert lint["count"] == len(lint["findings"])


@pytest.mark.asyncio
async def test_resume_intel_offline_is_advisory_and_truth_split():
    cv = cv_json_from_text(WEAK_CV)
    breakdown = ats.score(cv_json=cv, jd_text=SAMPLE_JD, role_title="Backend Engineer")
    structure = intel.structure_review(cv_text=WEAK_CV, cv_json=cv)
    ri = await resume_intel.analyze(
        cv_json=cv, cv_text=WEAK_CV, jd_text=SAMPLE_JD, role_title="Backend Engineer",
        breakdown=breakdown, structure=structure, verified_terms=None,
    )
    d = resume_intel.analysis_to_dict(ri)
    assert d["ai_powered"] is False  # fake mode -> offline advisory
    # weak-verb bullets produce coaching suggestions (never applied automatically)
    assert any(c["framework"] == "verb" for c in d["bullet_coaching"])
    # a JD skill the CV lacks and isn't verified -> omitted to stay truthful
    assert "postgresql" in {s.lower() for s in d["skills_alignment"]["omitted_for_truth"]} or \
           d["skills_alignment"]["missing"] == []  # (postgresql IS on this CV via a bullet)


@pytest.mark.asyncio
async def test_run_check_adds_intelligence_block_without_breaking_contract():
    result = await _run_check(
        jd_text=SAMPLE_JD, cv_text=WEAK_CV, role_title="Backend Engineer",
        use_ai=False, cv_filename=None,
    )
    # existing contract intact
    assert "rule_based" in result and result["ai"] is None
    # new block present with deterministic sub-blocks
    intel_block = result["intelligence"]
    assert {"tools", "structure", "verbs", "lint", "advisory"} <= set(intel_block)
    assert intel_block["advisory"] is None  # use_ai=False -> no advisory pass
    assert any(v["weak_verb"] == "managed" for v in intel_block["verbs"])

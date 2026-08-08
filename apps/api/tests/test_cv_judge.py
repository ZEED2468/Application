"""LLM judgment layer — semantic JD-coverage rescue + fit verdict, on the deterministic floor.

Offline it no-ops (run.judgment stays None). With the judge monkeypatched live: a JD term the
exact-keyword scan missed ("kubernetes") but the CV shows as "K8s" is rescued (evidence verbatim +
verifier confirms) and audited; a rescue whose quote is NOT in the CV is dropped by door #1; a
rescue the verifier won't confirm is dropped by door #2; and — the load-bearing invariant — the
deterministic score and the release decision are identical with or without the judge.
"""

import json

import pytest
from sqlalchemy import select

from app.core.enums import RunState
from app.cv_engine.render.compile import has_compiler
from app.cv_engine.runs.machine import run_pipeline
from app.cv_engine.runs.models import CvRunStep
from app.llm import client
from tests.helpers import seed_hunter

# "kubernetes" is a JD requirement the CV never spells out — it says "K8s" instead, so the
# exact-token scan marks it missing. "go"/"postgres" match; that is the semantic-rescue gap.
JUDGE_CV = {
    "headline": "Backend Engineer",
    "summary": "Backend engineer building production systems in Go.",
    "skills": ["Go", "Docker", "Postgres"],
    "experience": [{
        "title": "Backend Engineer", "company": "Streamline", "dates": "2020 -- 2024",
        "bullets": [
            "Operated and scaled K8s clusters in production",
            "Built Go microservices backed by Postgres",
        ],
    }],
    "links": {"github": "https://github.com/adahunter"},
}
LEDGER = [
    {"text": "Backend engineer building production systems in Go."},
    {"text": "Backend Engineer at Streamline 2020 2024. Operated and scaled K8s clusters "
             "in production. Built Go microservices backed by Postgres."},
    {"text": "Go Docker Postgres"},
    {"text": "https://github.com/adahunter"},
]
JD = (
    "Requirements:\n"
    "- Strong experience with Kubernetes for container orchestration\n"
    "- Proficiency in Go and Postgres in production\n"
    "- Familiarity with Terraform is a plus\n"
)

_LIVE = {"cv_judge", "cv_judge_verify", "ats_analyze"}   # judge live; cv_repair stays offline


def _canned(*, rescue, confirm=True):
    async def _fn(system, prompt, **k):
        if "audit whether a CV" in system:                 # rescue_coverage
            return json.dumps({"covered": rescue})
        if "strict fact-checker" in system:                # confirms — door #2
            return json.dumps({"demonstrated": bool(confirm)})
        if "ATS-style resume reviewer" in system:          # ats_analyze — the fit verdict
            return json.dumps({
                "fit_score": 62, "fit_summary": "Solid backend fit.",
                "strengths": ["Go", "Postgres"], "gaps": [],
                "recommendations": [], "false_positives": [], "verdict": "Moderate fit",
            })
        return None
    return _fn


def _go_live(monkeypatch, canned):
    monkeypatch.setattr(client, "is_live", lambda feature=None: feature in _LIVE)
    monkeypatch.setattr(client, "try_complete_text", canned)


def _input(cv=None):
    return {"cv_json": cv or {**JUDGE_CV}, "ledger": LEDGER, "jd_text": JD,
            "role_title": "Backend Engineer", "name": "Ada Hunter"}


def _covered(run) -> list[str]:
    return [r["keyword"] for r in run.judgment["coverage"]["semantic_covered"]]


async def test_offline_judgment_is_a_no_op(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input())
    # No LLM → judgment is never written; the deterministic run stands alone.
    assert run.judgment is None


@pytest.mark.skipif(not has_compiler(), reason="the judge needs a real artifact to score")
async def test_semantic_rescue_lands_and_is_audited(session, monkeypatch):
    user, _ = await seed_hunter(session)
    _go_live(monkeypatch, _canned(
        rescue=[{"keyword": "kubernetes", "evidence": "scaled K8s clusters in production"}]))
    run = await run_pipeline(session, user_id=user.id, input=_input())

    cov = run.judgment["coverage"]
    assert "kubernetes" in _covered(run)                       # rescued under another name
    assert "kubernetes" not in cov["still_missing"]            # and removed from the gap list
    assert run.judgment["fit"]["verdict"] == "Moderate fit"    # advisory fit verdict present
    # Judgment never relaxes the floor: the artifact still released on the gate + deterministic set.
    assert run.state == RunState.released and run.score is not None
    step = (await session.execute(
        select(CvRunStep).where(
            CvRunStep.run_id == run.id, CvRunStep.state == RunState.judged,
            CvRunStep.prompt_version.isnot(None),
        )
    )).scalars().first()
    assert step is not None and step.prompt_version == "cv_judge.v1"


@pytest.mark.skipif(not has_compiler(), reason="the judge needs a real artifact to score")
async def test_fabricated_quote_is_rejected_by_door_one(session, monkeypatch):
    user, _ = await seed_hunter(session)
    # The verifier is fooled (confirm=True), but the cited quote is nowhere in the CV.
    _go_live(monkeypatch, _canned(
        rescue=[{"keyword": "kubernetes",
                 "evidence": "Delivered a full Kubernetes platform migration across 12 clusters"}]))
    run = await run_pipeline(session, user_id=user.id, input=_input())

    assert "kubernetes" not in _covered(run)                   # unverifiable quote never lands
    assert "kubernetes" in run.judgment["coverage"]["still_missing"]


@pytest.mark.skipif(not has_compiler(), reason="the judge needs a real artifact to score")
async def test_verifier_drops_unconfirmed_rescue(session, monkeypatch):
    user, _ = await seed_hunter(session)
    # Quote is verbatim (door #1 passes) but the verifier refuses the semantic leap (door #2).
    _go_live(monkeypatch, _canned(
        rescue=[{"keyword": "kubernetes", "evidence": "scaled K8s clusters in production"}],
        confirm=False))
    run = await run_pipeline(session, user_id=user.id, input=_input())

    assert "kubernetes" not in _covered(run)
    assert "kubernetes" in run.judgment["coverage"]["still_missing"]


@pytest.mark.skipif(not has_compiler(), reason="needs a real artifact to compare scores")
async def test_score_and_release_are_unchanged_by_judgment(session, monkeypatch):
    user, _ = await seed_hunter(session)
    offline = await run_pipeline(session, user_id=user.id, input=_input())
    _go_live(monkeypatch, _canned(
        rescue=[{"keyword": "kubernetes", "evidence": "scaled K8s clusters in production"}]))
    judged = await run_pipeline(session, user_id=user.id, input=_input())

    # The judge is advisory: same input → identical deterministic score + terminal state.
    assert offline.judgment is None and judged.judgment is not None
    assert judged.score == offline.score
    assert judged.state == offline.state

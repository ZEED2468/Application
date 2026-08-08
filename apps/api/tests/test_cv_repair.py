"""Agent repair loop — bounded, truth-safe LLM rewrites behind the deterministic floor.

Offline it no-ops (fixtures stay green, covered elsewhere). With the LLM monkeypatched live:
a confirmed rewrite resolves the flaw + is audited; a rewrite that invents a number is
rejected by the grounding seal; a rewrite the judge won't confirm is dropped; an over-length
CV is trimmed to fit (removal-only).
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

WEAK_CV = {
    "headline": "Backend Engineer",
    "summary": "Backend engineer who builds production systems in Go.",
    "skills": ["Go", "Kubernetes", "Postgres"],
    "experience": [{
        "title": "Backend Engineer", "company": "Streamline", "dates": "2020 -- 2024",
        "bullets": ["Managed the backend team", "Built Go microservices"],
    }],
    "links": {"github": "https://github.com/adahunter"},
}
LEDGER = [
    {"text": "Backend engineer who builds production systems in Go."},
    {"text": "Backend Engineer at Streamline 2020 2024. Managed the backend team. "
             "Led the backend team. Built Go microservices."},
    {"text": "Go Kubernetes Postgres"}, {"text": "https://github.com/adahunter"},
]


def _canned(bullet_rewrite, *, judge=True, trimmed=None):
    async def _fn(system, prompt, **k):
        if "fact-checker" in system:                       # the entailment judge
            return '{"supported": true}' if judge else '{"supported": false}'
        if "Trim this CV" in system and trimmed is not None:
            return json.dumps(trimmed)
        return json.dumps({"summary": None, "bullets": [bullet_rewrite]})   # repair_draft
    return _fn


def _go_live(monkeypatch, canned):
    monkeypatch.setattr(client, "is_live", lambda feature=None: True)
    monkeypatch.setattr(client, "try_complete_text", canned)


def _input(cv):
    return {"cv_json": cv, "ledger": LEDGER, "jd_text": "Go Kubernetes backend",
            "name": "Ada Hunter"}


async def test_offline_repair_is_a_no_op(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input({**WEAK_CV}))
    # No LLM → the weak-verb bullet is untouched and strong_verbs is not resolved.
    assert run.input["cv_json"]["experience"][0]["bullets"][0] == "Managed the backend team"
    assert "structure.strong_verbs" not in run.delta.get("resolved", [])
    assert not any(f["rule_id"].startswith("agent.") for f in run.delta.get("fixed", []))


@pytest.mark.skipif(not has_compiler(), reason="needs tectonic to release")
async def test_live_rewrite_resolves_and_is_audited(session, monkeypatch):
    user, _ = await seed_hunter(session)
    _go_live(monkeypatch, _canned(
        {"original": "Managed the backend team", "rewrite": "Led the backend team"}))
    run = await run_pipeline(session, user_id=user.id, input=_input({**WEAK_CV}))

    assert run.input["cv_json"]["experience"][0]["bullets"][0] == "Led the backend team"
    assert "structure.strong_verbs" in run.delta["resolved"]
    assert any(f["rule_id"] == "agent.rewrite_bullet" and f["after"] == "Led the backend team"
               for f in run.delta["fixed"])
    step = (await session.execute(
        select(CvRunStep).where(
            CvRunStep.run_id == run.id, CvRunStep.state == RunState.patching,
            CvRunStep.prompt_version.isnot(None),
        )
    )).scalars().first()
    assert step is not None and step.prompt_version == "cv_repair.v1"


async def test_fabricated_rewrite_is_rejected_by_the_grounding_seal(session, monkeypatch):
    user, _ = await seed_hunter(session)
    # The judge is fooled (canned yes), but the rewrite invents "250%" — grounding must reject it.
    _go_live(monkeypatch, _canned(
        {"original": "Managed the backend team", "rewrite": "Boosted output by 250%"}))
    run = await run_pipeline(session, user_id=user.id, input=_input({**WEAK_CV}))

    assert "250" not in json.dumps(run.input["cv_json"])           # the fabrication never landed
    assert run.input["cv_json"]["experience"][0]["bullets"][0] == "Managed the backend team"
    assert not any(v["rule_id"].startswith("grounding.") for v in run.violations)


async def test_entailment_judge_drops_unconfirmed_rewrite(session, monkeypatch):
    user, _ = await seed_hunter(session)
    _go_live(monkeypatch, _canned(
        {"original": "Managed the backend team", "rewrite": "Led a team of engineers"},
        judge=False))  # judge refutes → the rewrite is dropped before it's applied
    run = await run_pipeline(session, user_id=user.id, input=_input({**WEAK_CV}))

    assert run.input["cv_json"]["experience"][0]["bullets"][0] == "Managed the backend team"
    assert not any(f["rule_id"] == "agent.rewrite_bullet" for f in run.delta.get("fixed", []))


@pytest.mark.skipif(not has_compiler(), reason="page-fit needs real renders")
async def test_page_fit_trims_to_the_limit(session, monkeypatch):
    user, _ = await seed_hunter(session)
    # A long CV that overruns the 1-page 'compact' template.
    big_bullets = [
        f"Delivered a significant production improvement number {i} across the entire "
        f"platform, improving reliability and reducing operational toil for many teams"
        for i in range(40)
    ]
    big_cv = {**WEAK_CV, "experience": [{
        "title": "Backend Engineer", "company": "Streamline", "dates": "2020 -- 2024",
        "bullets": big_bullets,
    }]}
    trimmed = {**big_cv,
               "experience": [{**big_cv["experience"][0], "bullets": big_bullets[:2]}]}
    ledger = [
        {"text": " ".join(big_bullets) + " Backend engineer who builds systems in Go."},
        {"text": "Go Kubernetes Postgres https://github.com/adahunter Streamline 2020 2024"},
    ]

    _go_live(monkeypatch, _canned(
        {"original": "x", "rewrite": "x"}, trimmed=trimmed))
    run = await run_pipeline(
        session, user_id=user.id, template_ref="compact",
        input={"cv_json": big_cv, "ledger": ledger, "jd_text": "Go", "name": "Ada Hunter"},
    )
    # The trim was applied (subset) and the page-count violation is gone from the final set.
    assert any(f["rule_id"] == "agent.trim_to_fit" for f in run.delta.get("fixed", []))
    assert not any(v["rule_id"] == "rendered.page_count" for v in run.violations)
    assert len(run.input["cv_json"]["experience"][0]["bullets"]) == 2

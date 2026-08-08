"""Provenance graph + the run-detail/eval-pair surface (Slice 8).

Every change the engine records cites the ledger fact(s) it derived from; the inferred summary is
recorded as a source-cited change AND added to the ledger as a derived fact carrying derived_from;
and GET /cv/runs/{id} exposes the ordered step trail.
"""

import json
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.cv_runs import get_run_detail
from app.core.enums import PrincipalType, RunState
from app.core.errors import NotFoundError
from app.cv_engine.runs.machine import run_pipeline
from app.cv_engine.runs.models import CvRunStep
from app.deps import Principal
from app.llm import client
from tests.helpers import seed_hunter

_LIVE = {"cv_infer", "cv_infer_verify"}


def _principal(user) -> Principal:
    return Principal(id=user.id, type=PrincipalType.user, role="hunter", track_scope=[])


def _cv(*, summary="Backend engineer building production systems in Go."):
    cv: dict = {"headline": "Backend Engineer", "skills": ["Go", "Postgres"]}
    if summary:
        cv["summary"] = summary
    cv["experience"] = [{
        "title": "Backend Engineer", "company": "Streamline", "dates": "Jan 2020 - present",
        "bullets": ["Built Go microservices"],
    }]
    cv["links"] = {"github": "github.com/adahunter"}   # no scheme → tidy_links fixes it
    return cv


def _input(cv):
    return {"cv_json": cv, "jd_text": "Go Postgres backend", "role_title": "Backend Engineer",
            "name": "Ada Hunter"}


def _canned(summary, *, supported=True):
    async def _fn(system, prompt, **k):
        if "professional summary" in system:
            return json.dumps({"summary": summary})
        if "strict fact-checker" in system:
            return json.dumps({"supported": bool(supported)})
        return None
    return _fn


def _go_live(monkeypatch, canned):
    monkeypatch.setattr(client, "is_live", lambda feature=None: feature in _LIVE)
    monkeypatch.setattr(client, "try_complete_text", canned)


async def test_each_change_cites_its_source_fact(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv()))

    facts = run.ledger_snapshot["facts"]
    role_id = next(f["id"] for f in facts if f["kind"] == "role")
    link_id = next(f["id"] for f in facts if f["kind"] == "link")
    fixed = run.delta["fixed"]

    date_rec = next(f for f in fixed if f["rule_id"] == "structure.date_format")
    assert date_rec["source"] == [role_id]                 # the date fix traces to its role fact
    link_rec = next(f for f in fixed if f["field"] == "links.github")
    assert link_rec["source"] == [link_id]                 # the link fix traces to its link fact


async def test_inferred_summary_carries_provenance(session, monkeypatch):
    user, _ = await seed_hunter(session)
    _go_live(monkeypatch, _canned(
        "Backend engineer with Go and Postgres experience at Streamline."))
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv(summary="")))

    facts = run.ledger_snapshot["facts"]
    role_skill = [f["id"] for f in facts if f["kind"] in ("role", "skill")]
    infer_rec = next(f for f in run.delta["fixed"] if f["rule_id"] == "agent.infer_summary")
    assert infer_rec["source"] == role_skill               # composed from role + skill facts
    derived = next(f for f in facts if f.get("source") == "derived")
    assert derived["kind"] == "summary" and derived["derived_from"] == role_skill


async def test_run_detail_returns_the_ordered_step_trail(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv()))

    detail = await get_run_detail(run.id, _principal(user), session)
    assert detail["run_id"] == str(run.id) and "delta" in detail   # run fields present
    states = [s["state"] for s in detail["steps"]]
    assert states[:3] == ["ingested", "gap_analyzed", "diagnosed"]
    assert states[-1] in ("released", "needs_review")
    # The trail is the actual persisted step count, in creation order.
    n = (await session.execute(
        select(CvRunStep).where(CvRunStep.run_id == run.id)
    )).scalars().all()
    assert len(detail["steps"]) == len(n)


async def test_run_detail_404_on_unknown_run(session):
    user, _ = await seed_hunter(session)
    with pytest.raises(NotFoundError):
        await get_run_detail(uuid4(), _principal(user), session)


async def test_run_detail_state_matches_the_run(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv()))
    detail = await get_run_detail(run.id, _principal(user), session)
    assert detail["state"] == run.state.value
    assert run.state in (RunState.released, RunState.needs_review)


async def test_derived_arithmetic_ledger(session):
    # Two roles spanning 2018-2024 → a computed "6 years experience" metric fact (Slice 11).
    user, _ = await seed_hunter(session)
    cv = {
        "summary": "Backend engineer building systems.", "skills": ["Go", "Postgres"],
        "experience": [
            {"title": "Engineer", "company": "Streamline", "dates": "2018 -- 2020",
             "bullets": ["Built Go services"]},
            {"title": "Engineer", "company": "Northwind", "dates": "2021 -- 2024",
             "bullets": ["Ran Postgres"]},
        ],
        "links": {"github": "https://github.com/adahunter"},
    }
    run = await run_pipeline(
        session, user_id=user.id,
        input={"cv_json": cv, "jd_text": "Go Postgres", "name": "Ada Hunter"})

    facts = run.ledger_snapshot["facts"]
    metric = next(f for f in facts if f["kind"] == "metric")
    assert metric["text"] == "6 years experience" and metric["source"] == "derived"
    role_ids = [f["id"] for f in facts if f["kind"] == "role"]
    # It aggregates every role, and its derived_from edges point at real ledger facts (closure).
    assert metric["derived_from"] == role_ids
    assert set(metric["derived_from"]) <= {f["id"] for f in facts}

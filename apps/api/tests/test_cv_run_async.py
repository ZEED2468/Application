"""Slice 12: off-request runs. POST /cv/runs/async creates an INGESTED run + hands it to a worker;
the worker's `drive_run` coordinates it to a terminal state. The sync endpoints are unchanged.
"""

from uuid import UUID

import app.api.cv_runs as cv_runs
from app.core.enums import RunState
from app.cv_engine.runs.machine import submit_run
from app.cv_engine.runs.models import CvRun
from app.cv_engine.runs.tasks import drive_run
from tests.helpers import seed_hunter

_CV = {
    "summary": "Backend engineer building production systems in Go.",
    "skills": ["Go", "Postgres"],
    "experience": [{"title": "Backend Engineer", "company": "Streamline", "dates": "2020 -- 2024",
                    "bullets": ["Built Go microservices"]}],
    "links": {"github": "https://github.com/adahunter"},
}


async def test_async_submit_returns_an_ingested_run(session, monkeypatch):
    monkeypatch.setattr(cv_runs, "emit", lambda *a, **k: None)  # no broker in tests
    user, _ = await seed_hunter(session)
    body = cv_runs.RunRequest(cv_json={**_CV}, jd_text="Go Postgres", name="Ada Hunter")

    result = await cv_runs.create_cv_run_async(body, user, session)

    assert result["state"] == "ingested"          # returns immediately, not driven yet
    run = await session.get(CvRun, UUID(result["run_id"]))
    assert run is not None and run.state is RunState.ingested


async def test_drive_run_coordinates_to_terminal(session):
    user, _ = await seed_hunter(session)
    run = await submit_run(
        session, user_id=user.id,
        input={"cv_json": {**_CV}, "jd_text": "Go Postgres", "name": "Ada Hunter"})
    assert run.state is RunState.ingested          # created, not yet coordinated

    await drive_run(session, run.id)
    assert run.state in (RunState.released, RunState.needs_review)

    await drive_run(session, run.id)               # idempotent: a non-INGESTED run is left alone
    assert run.state in (RunState.released, RunState.needs_review)

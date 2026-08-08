"""Off-request execution of a CV run (Slice 12).

The synchronous POST endpoints run the pipeline inline; the async submit path instead creates the
run (state INGESTED), emits CV_RUN_SUBMITTED, and returns immediately. This task drives that run to
a terminal state in a worker, so a long render never blocks the request. The client polls
`GET /cv/runs/{id}` for progress. Mirrors the pipelines' sync-task → async `_work` →
run_with_session bridge.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from app.core.enums import RunState
from app.cv_engine.runs.machine import coordinate
from app.cv_engine.runs.models import CvRun
from app.events.names import CV_RUN_SUBMITTED
from app.workers.celery_app import UserScopedTask, celery_app
from app.workers.runner import run_with_session

log = structlog.get_logger(__name__)


async def drive_run(session, run_id: UUID) -> None:
    """Coordinate a freshly-created (INGESTED) run to a terminal state. Idempotent: a run that a
    worker already picked up (not INGESTED) is left alone."""
    run = await session.get(CvRun, run_id)
    if run is None or run.state is not RunState.ingested:
        return
    await coordinate(session, run)


@celery_app.task(name=CV_RUN_SUBMITTED, base=UserScopedTask, bind=True)
def run_cv_engine(self, payload: dict) -> None:
    run_id = UUID(payload["run_id"])
    run_with_session(lambda session: drive_run(session, run_id))

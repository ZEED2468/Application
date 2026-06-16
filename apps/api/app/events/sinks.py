"""No-op consumers for notification events that have no business subscriber yet.

Events like `job.scored`, `cv.generated`, `outreach.sent`, and the `chat.*` events
are emitted for observability/analytics + future subscribers. Without a registered
task, a Celery worker logs "received unregistered task" and rejects them. These
sinks make the worker accept (and log) them cleanly. A real subscriber can replace
any sink by binding a task to the same event name in its pipeline.
"""

from __future__ import annotations

import structlog

from app.events.names import (
    CHAT_APPLICATION_CREATED,
    CHAT_CV_MATCHED,
    CHAT_PROMPTS_RAISED,
    CHAT_SESSION_STARTED,
    CV_GENERATED,
    JOB_SCORED,
    OUTREACH_SENT,
)
from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)

# Events with no dedicated consumer (yet).
NOTIFICATION_EVENTS = [
    JOB_SCORED,
    CV_GENERATED,
    OUTREACH_SENT,
    CHAT_SESSION_STARTED,
    CHAT_CV_MATCHED,
    CHAT_PROMPTS_RAISED,
    CHAT_APPLICATION_CREATED,
]


def _make_sink(event_name: str):
    @celery_app.task(name=event_name)
    def _sink(payload: dict | None = None) -> None:
        log.info("event.sink", event_name=event_name)

    return _sink


SINKS = {name: _make_sink(name) for name in NOTIFICATION_EVENTS}

"""The single Celery application. Workers + beat run off this instance.

Task modules are autodiscovered from each pipeline + email subsystem so that
binding `@celery_app.task(name=EVENT)` in any pipeline registers a consumer.
"""

import structlog
from celery import Celery, Task

from app.config import settings

celery_app = Celery(
    "jd",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="default",
)

# Queue routing: email + render get dedicated queues for rate limiting / isolation.
celery_app.conf.task_routes = {
    "task.email.*": {"queue": "email"},
    "task.apply.render*": {"queue": "render"},
    "task.respond.poll*": {"queue": "poll"},
}

log = structlog.get_logger(__name__)


class UserScopedTask(Task):
    """Base task that binds user_id from the event payload into the log context."""

    def __call__(self, *args, **kwargs):
        payload = kwargs.get("payload") or (args[0] if args else None)
        user_id = payload.get("user_id") if isinstance(payload, dict) else None
        structlog.contextvars.bind_contextvars(user_id=user_id, task=self.name)
        try:
            return super().__call__(*args, **kwargs)
        finally:
            structlog.contextvars.clear_contextvars()


# Autodiscover consumer + internal task modules.
celery_app.autodiscover_tasks(
    packages=[
        "app.pipelines.apply",
        "app.pipelines.outreach",
        "app.pipelines.respond",
        "app.email",
    ],
    related_name="tasks",
)

# Import the beat schedule (registers periodic tasks).
from app.workers import beat_schedule  # noqa: E402,F401

# Register no-op sinks for notification events with no dedicated consumer, so the
# worker accepts them instead of logging "received unregistered task".
from app.events import sinks  # noqa: E402,F401

"""Event bus — thin wrapper over Celery send_task. Producers never import
consumers; they emit a named event with a validated payload."""

from __future__ import annotations

import structlog

from app.events.contracts import CONTRACTS, EventPayload

log = structlog.get_logger(__name__)


def emit(event_name: str, payload: EventPayload) -> None:
    """Validate the payload against its contract and publish it."""
    schema = CONTRACTS.get(event_name)
    if schema is None:
        raise ValueError(f"Unknown event: {event_name}")
    # Re-validate to guarantee the payload matches the frozen contract.
    validated = schema.model_validate(payload.model_dump())

    # Imported lazily so producers don't pull in the worker at import time.
    from app.workers.celery_app import celery_app

    celery_app.send_task(
        event_name,
        kwargs={"payload": validated.model_dump(mode="json")},
    )
    log.info("event.emitted", event=event_name, user_id=str(validated.user_id))

"""Pipeline B (Outreach) consumers + sequencer. Seam for Engineer 2.

Builds against application_submitted: Apollo lookup -> hook-finder -> draft ->
governed send -> follow-up sequencer.
"""

from __future__ import annotations

import structlog

from app.events.names import APPLICATION_SUBMITTED
from app.workers.celery_app import UserScopedTask, celery_app

log = structlog.get_logger(__name__)


@celery_app.task(name=APPLICATION_SUBMITTED, base=UserScopedTask, bind=True)
def on_application_submitted(self, payload: dict) -> None:
    """Find people -> enrich hook -> draft -> queue for VA review/governed send."""
    log.info("outreach.application_submitted.received", app_id=payload.get("application_id"))
    # TODO(eng2): Apollo lookup, hookfinder, draft, route through email.governor.


@celery_app.task(name="task.outreach.sequencer_tick", bind=True)
def sequencer_tick(self) -> None:
    """Beat: 4d no reply -> followup1 -> 5d -> followup2 -> stop."""
    log.info("outreach.sequencer.tick")
    # TODO(eng2): scan outreach WHERE status=sent AND next_action_at<=now.

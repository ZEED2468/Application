"""Pipeline C (Respond) consumers + inbox poll. Seam for Engineer 3.

Builds against reply_received: match -> classify -> dossier -> push to VA ->
relay VA reply as threaded email.
"""

from __future__ import annotations

import structlog

from app.events.names import REPLY_RECEIVED
from app.workers.celery_app import UserScopedTask, celery_app

log = structlog.get_logger(__name__)


@celery_app.task(name=REPLY_RECEIVED, base=UserScopedTask, bind=True)
def on_reply_received(self, payload: dict) -> None:
    """Classify -> assemble dossier -> push to assigned VA via bridge."""
    log.info("respond.reply_received.received", reply_id=payload.get("reply_id"))
    # TODO(eng3): classify routine/substantive, build dossier, bridge push.


@celery_app.task(name="task.respond.poll_inboxes", bind=True)
def poll_inboxes(self) -> None:
    """Beat: poll the 9 inboxes as a backup to Resend inbound webhooks."""
    log.info("respond.poll_inboxes.tick")
    # TODO(eng3): poll, match, persist reply, emit reply.received (idempotent).

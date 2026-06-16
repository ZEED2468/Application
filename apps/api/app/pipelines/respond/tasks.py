"""Pipeline C (Respond) consumers + inbox poll. Seam for Engineer 3.

Builds against reply_received: match -> classify -> dossier -> push to VA ->
relay VA reply as threaded email.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from app.events.names import REPLY_RECEIVED
from app.pipelines.respond import service
from app.workers.celery_app import UserScopedTask, celery_app
from app.workers.runner import run_with_session

log = structlog.get_logger(__name__)


@celery_app.task(name=REPLY_RECEIVED, base=UserScopedTask, bind=True)
def on_reply_received(self, payload: dict) -> None:
    """Classify -> assemble dossier -> push to assigned VA via bridge."""
    reply_id = UUID(payload["reply_id"])

    async def _work(session):
        await service.process_reply(session, reply_id=reply_id)

    run_with_session(_work)


@celery_app.task(name="task.respond.poll_inboxes", bind=True)
def poll_inboxes(self) -> None:
    """Beat: poll the 9 inboxes as a backup to Resend inbound webhooks.

    The webhook path (app/api/webhooks/resend.py) is primary; this is the safety
    net. Real IMAP/provider polling drops in here; ingest is idempotent on
    message_id so double-delivery is harmless.
    """
    log.info("respond.poll_inboxes.tick")

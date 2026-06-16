"""Pipeline B (Outreach) consumers + sequencer. Seam for Engineer 2.

Builds against application_submitted: Apollo lookup -> hook-finder -> draft ->
governed send -> follow-up sequencer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.enums import OutreachStatus, SequenceStep
from app.events.names import APPLICATION_SUBMITTED
from app.models.application import Application
from app.models.outreach import Outreach
from app.pipelines.outreach import service
from app.workers.celery_app import UserScopedTask, celery_app
from app.workers.runner import run_with_session

log = structlog.get_logger(__name__)


@celery_app.task(name=APPLICATION_SUBMITTED, base=UserScopedTask, bind=True)
def on_application_submitted(self, payload: dict) -> None:
    """Find people -> enrich hook -> draft -> queue for VA review/governed send."""
    application_id = UUID(payload["application_id"])

    async def _work(session):
        application = await session.get(Application, application_id)
        if application is None:
            return
        await service.run_outreach(session, application=application)

    run_with_session(_work)


@celery_app.task(name="task.outreach.sequencer_tick", bind=True)
def sequencer_tick(self) -> None:
    """Beat: 4d no reply -> followup1 -> 5d -> followup2 -> stop.

    A reply flips outreach.status to `replied` (Pipeline C), excluding it here.
    """
    now = datetime.now(timezone.utc)

    async def _work(session):
        stmt = select(Outreach).where(
            Outreach.status == OutreachStatus.sent,
            Outreach.sequence_step != SequenceStep.stopped,
            Outreach.next_action_at.is_not(None),
            Outreach.next_action_at <= now,
        )
        due = list((await session.execute(stmt)).scalars().all())
        for prev in due:
            await service.advance_followup(session, prev=prev)
        log.info("outreach.sequencer.tick", advanced=len(due))

    run_with_session(_work)

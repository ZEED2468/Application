"""Email subsystem beat tasks: warm-up rollover + health scan."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.core.enums import OutreachStatus
from app.email import caps
from app.models.outreach import Outreach
from app.models.sending_domain import SendingDomain
from app.workers.celery_app import celery_app
from app.workers.runner import run_with_session

log = structlog.get_logger(__name__)


@celery_app.task(name="task.email.warmup_rollover", bind=True)
def warmup_rollover(self) -> None:
    """Daily: reset per-domain counters, advance warm-up stage, drain queued sends."""
    now = datetime.now(timezone.utc)

    async def _work(session):
        from app.pipelines.outreach import service as outreach_service

        domains = list((await session.execute(select(SendingDomain))).scalars().all())
        for d in domains:
            if caps.is_new_day(d.daily_count_date, now.date()):
                d.daily_sent_count = 0
                d.daily_count_date = now.date()
            d.warmup_stage = caps.stage_for_age(d.warmup_started_at, now)
        await session.flush()

        # Drain queued outreach now that today's caps have reset.
        queued = list((await session.execute(
            select(Outreach).where(
                Outreach.status == OutreachStatus.queued,
                Outreach.next_action_at.is_not(None),
                Outreach.next_action_at <= now,
            )
        )).scalars().all())
        for o in queued:
            await outreach_service.send_outreach(session, outreach_id=o.id)
        log.info("email.warmup_rollover", domains=len(domains), drained=len(queued))

    run_with_session(_work)


@celery_app.task(name="task.email.health_scan", bind=True)
def health_scan(self) -> None:
    """Hourly: re-evaluate per-domain health; auto-pause over threshold.

    Real-time bounce/complaint events arrive via the Resend events webhook
    (app/email/health.py) which already auto-pauses; this periodic pass would pull
    Google Postmaster aggregates as a backstop. No-op until creds are wired.
    """
    log.info("email.health_scan.tick")

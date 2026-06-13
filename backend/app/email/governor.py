"""Warm-up governor — THE single choke point every outbound email passes through.

No module may call the email provider directly; all sends route through
`governed_send`. It enforces, per domain, the warm-up daily cap and, per hunter,
the weekly cap. The sending_domain row is locked (SELECT ... FOR UPDATE) so two
workers can never jointly exceed the cap.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import OutreachStatus
from app.email import caps
from app.models.outreach import Outreach
from app.models.sending_domain import SendingDomain

log = structlog.get_logger(__name__)


class SendResult(str, enum.Enum):
    sent = "sent"
    deferred = "deferred"  # over a cap -> requeued for tomorrow
    paused = "paused"      # domain auto-paused for health


def _next_send_window(now: datetime) -> datetime:
    """Tomorrow 09:00 UTC (placeholder for per-hunter timezone)."""
    tomorrow = (now + timedelta(days=1)).date()
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0, tzinfo=timezone.utc)


async def _weekly_count(session: AsyncSession, user_id, now: datetime) -> int:
    since = now - timedelta(days=7)
    stmt = (
        select(func.count())
        .select_from(Outreach)
        .where(
            Outreach.user_id == user_id,
            Outreach.status == OutreachStatus.sent,
            Outreach.sent_at >= since,
        )
    )
    return int((await session.execute(stmt)).scalar_one())


async def governed_send(session: AsyncSession, outreach_id, *, send_fn) -> SendResult:
    """Attempt to send one outreach. `send_fn(outreach, domain) -> message_id` does
    the actual provider call; the governor decides whether it may run.

    The caller owns the surrounding transaction. We lock the domain row to
    serialize the cap check + increment.
    """
    now = datetime.now(timezone.utc)
    outreach = await session.get(Outreach, outreach_id)
    if outreach is None:
        raise ValueError(f"outreach {outreach_id} not found")

    # Lock the domain row — only writer of daily_sent_count.
    domain = (
        await session.execute(
            select(SendingDomain)
            .where(SendingDomain.id == outreach.sending_domain_id)
            .with_for_update()
        )
    ).scalar_one()

    if domain.is_paused:
        outreach.status = OutreachStatus.queued
        outreach.next_action_at = _next_send_window(now)
        log.warning("governor.paused", domain=domain.domain)
        return SendResult.paused

    # Roll the daily counter on date change.
    if caps.is_new_day(domain.daily_count_date, now.date()):
        domain.daily_sent_count = 0
        domain.daily_count_date = now.date()

    # Advance stage by warm-up age and compute today's cap.
    domain.warmup_stage = caps.stage_for_age(domain.warmup_started_at, now)
    cap = caps.daily_cap(domain.warmup_stage)

    weekly = await _weekly_count(session, outreach.user_id, now)

    if domain.daily_sent_count >= cap or weekly >= settings.weekly_cap_per_hunter:
        outreach.status = OutreachStatus.queued
        outreach.next_action_at = _next_send_window(now)
        log.info(
            "governor.deferred",
            domain=domain.domain,
            daily=domain.daily_sent_count,
            cap=cap,
            weekly=weekly,
        )
        return SendResult.deferred

    # Under both caps -> send and increment atomically (row is locked).
    message_id = await send_fn(outreach, domain)
    outreach.message_id = message_id
    outreach.status = OutreachStatus.sent
    outreach.sent_at = now
    domain.daily_sent_count += 1
    log.info("governor.sent", domain=domain.domain, daily=domain.daily_sent_count, cap=cap)
    return SendResult.sent

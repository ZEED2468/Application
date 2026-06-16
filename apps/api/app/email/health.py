"""Per-domain deliverability health — ingest provider bounce/complaint events and
auto-pause a domain that crosses a threshold."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sending_domain import SendingDomain

log = structlog.get_logger(__name__)

BOUNCE_PAUSE_THRESHOLD = 0.05      # 5% bounce rate
COMPLAINT_PAUSE_THRESHOLD = 0.001  # 0.1% spam-complaint rate


async def ingest_event(session: AsyncSession, *, domain_name: str, event_type: str) -> None:
    """Update counters from a Resend event; auto-pause unhealthy domains."""
    domain = (
        await session.execute(select(SendingDomain).where(SendingDomain.domain == domain_name))
    ).scalar_one_or_none()
    if domain is None:
        return

    if event_type in ("email.bounced", "bounced"):
        domain.bounce_rate = round(min(1.0, domain.bounce_rate + 0.01), 4)
    elif event_type in ("email.complained", "complained"):
        domain.complaint_rate = round(min(1.0, domain.complaint_rate + 0.001), 4)

    if (domain.bounce_rate >= BOUNCE_PAUSE_THRESHOLD
            or domain.complaint_rate >= COMPLAINT_PAUSE_THRESHOLD):
        if not domain.is_paused:
            domain.is_paused = True
            domain.pause_reason = f"auto-paused: {event_type} threshold crossed"
            log.warning("email.health.autopause", domain=domain.domain)

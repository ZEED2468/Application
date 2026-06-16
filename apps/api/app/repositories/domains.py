"""sending_domain access + a seeding helper (the 9 (user,track) rows)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DnsStatus, Track, WarmupStage
from app.models.sending_domain import SendingDomain


async def get_for_user_track(
    session: AsyncSession, *, user_id: UUID, track: Track
) -> SendingDomain | None:
    stmt = select(SendingDomain).where(
        SendingDomain.user_id == user_id, SendingDomain.track == track
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def ensure_domain(
    session: AsyncSession, *, user_id: UUID, track: Track, verified: bool = True
) -> SendingDomain:
    """Return the (user,track) sending domain, creating a seeded one if absent.

    Used so outreach can always resolve a domain in dev/tests. In production the 9
    domains are provisioned + verified via the admin flow before any real send.
    """
    domain = await get_for_user_track(session, user_id=user_id, track=track)
    if domain is not None:
        return domain
    # uuid7's leading hex is a timestamp (collides for same-ms users); use the
    # random tail so the (user, track) domain name is globally unique.
    name = f"{track.value}-{user_id.hex[-10:]}.jdmail.dev"
    status = DnsStatus.verified if verified else DnsStatus.pending
    domain = SendingDomain(
        user_id=user_id, track=track, domain=name,
        dkim_status=status, spf_status=status, dmarc_status=status,
        warmup_stage=WarmupStage.full if verified else WarmupStage.stage_1,
        warmup_started_at=datetime.now(timezone.utc),
    )
    session.add(domain)
    await session.flush()
    return domain


async def list_all(session: AsyncSession) -> list[SendingDomain]:
    stmt = select(SendingDomain).order_by(SendingDomain.user_id, SendingDomain.track)
    return list((await session.execute(stmt)).scalars().all())

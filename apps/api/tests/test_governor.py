"""Warm-up governor: daily cap enforcement, deferral, pause, and stage math."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.enums import OutreachStatus, Track, WarmupStage
from app.core.ids import new_id
from app.email import caps
from app.email.governor import SendResult, governed_send
from app.models.outreach import Outreach
from app.models.sending_domain import SendingDomain


async def _make_domain(session, *, started_days_ago=20, paused=False):
    user_id = new_id()
    domain = SendingDomain(
        user_id=user_id,
        track=Track.backend,
        domain="hunter-backend.example.com",
        warmup_started_at=datetime.now(timezone.utc) - timedelta(days=started_days_ago),
        is_paused=paused,
    )
    session.add(domain)
    await session.flush()
    return user_id, domain


async def _make_outreach(session, user_id, domain):
    o = Outreach(
        user_id=user_id,
        application_id=new_id(),
        contact_id=new_id(),
        sending_domain_id=domain.id,
        status=OutreachStatus.queued,
    )
    session.add(o)
    await session.flush()
    return o


async def _noop_send(outreach, domain):
    return "msg-" + outreach.id.hex[:8]


def test_stage_math():
    now = datetime.now(timezone.utc)
    assert caps.stage_for_age(now - timedelta(days=1)) is WarmupStage.stage_1
    assert caps.stage_for_age(now - timedelta(days=5)) is WarmupStage.stage_2
    assert caps.stage_for_age(now - timedelta(days=10)) is WarmupStage.stage_3
    assert caps.stage_for_age(now - timedelta(days=30)) is WarmupStage.full
    assert caps.daily_cap(WarmupStage.stage_1) == 5


@pytest.mark.asyncio
async def test_send_under_cap_increments(session):
    user_id, domain = await _make_domain(session, started_days_ago=1)  # stage_1, cap 5
    o = await _make_outreach(session, user_id, domain)
    result = await governed_send(session, o.id, send_fn=_noop_send)
    assert result is SendResult.sent
    assert domain.daily_sent_count == 1
    assert o.status is OutreachStatus.sent
    assert o.message_id


@pytest.mark.asyncio
async def test_defers_over_daily_cap(session):
    user_id, domain = await _make_domain(session, started_days_ago=1)  # cap 5
    domain.daily_sent_count = 5
    domain.daily_count_date = datetime.now(timezone.utc).date()
    o = await _make_outreach(session, user_id, domain)
    result = await governed_send(session, o.id, send_fn=_noop_send)
    assert result is SendResult.deferred
    assert o.status is OutreachStatus.queued
    assert o.next_action_at is not None


@pytest.mark.asyncio
async def test_paused_domain_defers(session):
    user_id, domain = await _make_domain(session, paused=True)
    o = await _make_outreach(session, user_id, domain)
    result = await governed_send(session, o.id, send_fn=_noop_send)
    assert result is SendResult.paused
    assert o.status is OutreachStatus.queued

"""Pipeline B: people -> hook -> draft -> governed send -> sequencer."""

import pytest

from app.core.enums import OutreachStatus, SequenceStep
from app.events import names
from app.email.governor import SendResult
from app.integrations import resend
from app.models.contact import Contact
from app.pipelines.outreach import service
from sqlalchemy import select
from tests.helpers import EventSink, seed_hunter, seed_submitted_application


@pytest.mark.asyncio
async def test_run_outreach_drafts_first_contact(session):
    user, _ = await seed_hunter(session)
    app = await seed_submitted_application(session, user=user)

    outreach = await service.run_outreach(session, application=app)
    assert outreach is not None
    assert outreach.status is OutreachStatus.review  # VA must review first contact
    assert outreach.sequence_step is SequenceStep.first
    assert outreach.subject and outreach.body
    # 2-3 contacts found; top is the engineer (priority).
    contacts = list((await session.execute(
        select(Contact).where(Contact.job_id == app.job_id)
    )).scalars().all())
    assert len(contacts) >= 2
    top = await session.get(Contact, outreach.contact_id)
    assert top.role_type == "engineer"
    assert top.hook  # hook enriched onto the contact


@pytest.mark.asyncio
async def test_send_outreach_goes_through_governor_and_emits(session):
    resend.SENT_LOG.clear()
    user, _ = await seed_hunter(session)
    app = await seed_submitted_application(session, user=user)
    outreach = await service.run_outreach(session, application=app)

    sink = EventSink()
    result = await service.send_outreach(session, outreach_id=outreach.id, emit=sink)
    assert result is SendResult.sent
    assert outreach.status is OutreachStatus.sent
    assert outreach.reply_address and outreach.reply_address.startswith("apply+")
    assert len(resend.SENT_LOG) == 1
    assert names.OUTREACH_SENT in sink.names()

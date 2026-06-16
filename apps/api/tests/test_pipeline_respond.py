"""Pipeline C: inbound match -> classify -> dossier -> bridge push -> relay."""

import pytest

from app.core.enums import DossierStatus, ReplyClassification, ThreadState
from app.email.governor import SendResult
from app.events import names
from app.integrations import bridge_client, resend
from app.models.contact import Contact
from app.pipelines.outreach import service as outreach_service
from app.pipelines.respond import service as respond_service
from tests.helpers import EventSink, seed_hunter, seed_submitted_application, seed_va


async def _sent_outreach(session, user):
    app = await seed_submitted_application(session, user=user)
    outreach = await outreach_service.run_outreach(session, application=app)
    await outreach_service.send_outreach(session, outreach_id=outreach.id, emit=EventSink())
    return app, outreach


@pytest.mark.asyncio
async def test_inbound_matches_via_signed_tag_and_emits(session):
    user, _ = await seed_hunter(session)
    _, outreach = await _sent_outreach(session, user)
    contact = await session.get(Contact, outreach.contact_id)

    sink = EventSink()
    reply = await respond_service.ingest_inbound(
        session, to_addr=outreach.reply_address, from_addr=contact.email,
        subject="Re: role", body="Can we schedule a call this week?",
        message_id="<inbound-1@corp>", emit=sink,
    )
    assert reply is not None
    assert names.REPLY_RECEIVED in sink.names()


@pytest.mark.asyncio
async def test_process_reply_builds_dossier_and_pushes_to_va(session):
    bridge_client.PUSH_LOG.clear()
    user, _ = await seed_hunter(session)
    va = await seed_va(session, user=user)
    _, outreach = await _sent_outreach(session, user)
    contact = await session.get(Contact, outreach.contact_id)

    reply = await respond_service.ingest_inbound(
        session, to_addr=outreach.reply_address, from_addr=contact.email,
        subject="Re: role", body="Thanks! Can we schedule a call?",
        message_id="<inbound-2@corp>", emit=EventSink(),
    )
    dossier = await respond_service.process_reply(session, reply_id=reply.id)
    assert dossier is not None
    assert dossier.va_id == va.id
    # "schedule" -> routine -> auto-draft attached.
    assert reply.classification is ReplyClassification.routine
    assert dossier.suggested_reply
    assert dossier.bridge_message_ref
    assert len(bridge_client.PUSH_LOG) == 1


@pytest.mark.asyncio
async def test_va_reply_relays_through_governor(session):
    resend.SENT_LOG.clear()
    user, _ = await seed_hunter(session)
    va = await seed_va(session, user=user)
    _, outreach = await _sent_outreach(session, user)
    contact = await session.get(Contact, outreach.contact_id)
    reply = await respond_service.ingest_inbound(
        session, to_addr=outreach.reply_address, from_addr=contact.email,
        subject="Re: role", body="Can we schedule a call?", message_id="<in-3@corp>",
        emit=EventSink(),
    )
    dossier = await respond_service.process_reply(session, reply_id=reply.id)

    before = len(resend.SENT_LOG)
    result = await respond_service.relay_va_reply(
        session, va_jid=va.whatsapp_jid, in_reply_to_ref=dossier.bridge_message_ref,
        text="Sure — I'm free Thursday afternoon.",
    )
    assert result is SendResult.sent
    assert len(resend.SENT_LOG) == before + 1
    assert dossier.status is DossierStatus.relayed

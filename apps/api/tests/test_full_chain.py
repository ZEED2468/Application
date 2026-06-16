"""Capstone: the autonomous path threaded A -> B -> C end-to-end (all fakes),
asserting every core event fires and the conversation completes."""

import pytest

from app.core.enums import JobStatus
from app.events import names
from app.models.contact import Contact
from app.pipelines.apply import service as apply_service
from app.pipelines.outreach import service as outreach_service
from app.pipelines.respond import service as respond_service
from tests.helpers import EventSink, seed_hunter, seed_va


@pytest.mark.asyncio
async def test_autonomous_chain_a_to_b_to_c(session):
    user, profile = await seed_hunter(session)
    va = await seed_va(session, user=user)
    sink = EventSink()

    # --- A: discover -> classify -> score -> generate -> submit ---
    jobs = await apply_service.discover_for_user(session, user_id=user.id, profile=profile, emit=sink)
    job = jobs[0]
    apply_service.classify_track(job)
    await apply_service.score_relevance(session, job=job, profile=profile, emit=sink)
    cv = await apply_service.generate_cv(session, job=job, profile=profile, emit=sink)
    assert cv.ats_score is not None  # shared engine ran ATS on the autonomous path too
    application = await apply_service.submit_application(
        session, user_id=user.id, job=job, generated_cv=cv, va_id=va.id, emit=sink
    )

    # --- B: outreach draft -> governed send ---
    outreach = await outreach_service.run_outreach(session, application=application, emit=sink)
    await outreach_service.send_outreach(session, outreach_id=outreach.id, emit=sink)

    # --- C: inbound -> dossier/bridge -> relay ---
    contact = await session.get(Contact, outreach.contact_id)
    reply = await respond_service.ingest_inbound(
        session, to_addr=outreach.reply_address, from_addr=contact.email,
        subject="Re: role", body="Thanks — can we schedule a call?",
        message_id="<chain-in@corp>", emit=sink,
    )
    dossier = await respond_service.process_reply(session, reply_id=reply.id, emit=sink)
    await respond_service.relay_va_reply(
        session, va_jid=va.whatsapp_jid, in_reply_to_ref=dossier.bridge_message_ref,
        text="Thursday works.", emit=sink,
    )

    # Every core event fired, in order across the three pipelines.
    fired = sink.names()
    for evt in (names.JOB_DISCOVERED, names.JOB_SCORED, names.CV_GENERATED,
                names.APPLICATION_SUBMITTED, names.OUTREACH_SENT, names.REPLY_RECEIVED):
        assert evt in fired, f"missing {evt}"
    assert job.status is JobStatus.submitted

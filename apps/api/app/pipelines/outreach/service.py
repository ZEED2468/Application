"""Pipeline B orchestration: people -> hook -> draft -> governed send -> sequencer.

First contact is drafted in `review` status (a VA approves before send, per PRD).
Follow-ups auto-send. ALL sends route through the warm-up governor.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog

from app.core.enums import OutreachStatus, SequenceStep, ThreadState, Track
from app.email import sender as email_sender
from app.email.governor import SendResult, governed_send
from app.events import names
from app.events.bus import emit as _real_emit
from app.events.contracts import OutreachSent
from app.integrations import apollo
from app.llm import draft_email, hookfinder
from app.models.application import Application
from app.models.contact import Contact
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.thread import Thread
from app.models.user import User
from app.repositories import applications as app_repo
from app.repositories import domains as domains_repo
from app.repositories import profiles as profiles_repo

log = structlog.get_logger(__name__)

# Follow-up cadence (PRD §5.3): no reply ~4d -> fu1 -> ~5d -> fu2 -> stop.
FOLLOWUP1_DAYS = 4
FOLLOWUP2_DAYS = 5


async def run_outreach(session, *, application: Application, emit=_real_emit) -> Outreach | None:
    """On application.submitted: find people, enrich a hook, draft first contact."""
    job = await session.get(Job, application.job_id)
    user = await session.get(User, application.user_id)
    track = job.track or Track.general
    profile = await profiles_repo.get_by_user_track(session, user_id=user.id, track=track)
    links = profile.links if profile else {}

    domain = await domains_repo.ensure_domain(session, user_id=user.id, track=track)

    people = await apollo.lookup_people(company=job.company, role_title=job.role_title or job.title)
    if not people:
        log.warning("outreach.no_people", company=job.company)
        return None

    hook = await hookfinder.find_hook(
        company=job.company, track=track, job_description=job.description
    )

    contacts: list[Contact] = []
    for p in people:
        c = Contact(
            user_id=user.id, job_id=job.id, company=job.company, full_name=p.full_name,
            title=p.title, role_type=p.role_type, email=p.email, linkedin=p.linkedin,
            apollo_id=p.apollo_id, hook=hook.text, confidence=p.confidence,
        )
        session.add(c)
        contacts.append(c)
    await session.flush()

    top = contacts[0]  # highest priority (engineer > hm > recruiter)
    thread = Thread(
        user_id=user.id, application_id=application.id, contact_id=top.id,
        sending_domain_id=domain.id, reply_address="", state=ThreadState.open,
    )
    session.add(thread)
    await session.flush()

    subject, body = await draft_email.draft_outreach(
        candidate_name=user.name, company=job.company,
        role_title=job.role_title or job.title, track=track, hook=hook,
        links=links, contact_name=top.full_name or "",
    )
    outreach = Outreach(
        user_id=user.id, application_id=application.id, contact_id=top.id,
        sending_domain_id=domain.id, thread_id=thread.id,
        sequence_step=SequenceStep.first, status=OutreachStatus.review,
        subject=subject, body=body,
    )
    session.add(outreach)
    await session.flush()
    app_repo.record_event(
        session, application=application, kind="outreach_drafted",
        detail={"contact": top.email, "step": "first"},
    )
    log.info("outreach.drafted", outreach_id=str(outreach.id), contact=top.email)
    return outreach


async def send_outreach(session, *, outreach_id: UUID, emit=_real_emit) -> SendResult:
    """VA-approved send (or sequencer follow-up). Routes through the governor."""
    outreach = await session.get(Outreach, outreach_id)
    contact = await session.get(Contact, outreach.contact_id)
    job = await session.get(Job, (await session.get(Application, outreach.application_id)).job_id)
    user = await session.get(User, outreach.user_id)

    send_fn = email_sender.make_send_fn(
        to_email=contact.email, candidate_name=user.name, job_id=job.id,
    )
    result = await governed_send(session, outreach_id, send_fn=send_fn)

    if result is SendResult.sent:
        thread = await session.get(Thread, outreach.thread_id)
        if thread is not None:
            thread.reply_address = outreach.reply_address or thread.reply_address
            thread.root_message_id = outreach.message_id
            thread.last_outbound_at = datetime.now(timezone.utc)
        outreach.next_action_at = datetime.now(timezone.utc) + timedelta(days=FOLLOWUP1_DAYS)
        application = await session.get(Application, outreach.application_id)
        app_repo.record_event(
            session, application=application, kind="outreach_sent",
            detail={"step": outreach.sequence_step.value, "to": contact.email},
        )
        emit(
            names.OUTREACH_SENT,
            OutreachSent(user_id=outreach.user_id, outreach_id=outreach.id,
                         application_id=outreach.application_id, contact_id=outreach.contact_id),
        )
    log.info("outreach.send", outreach_id=str(outreach_id), result=result.value)
    return result


_NEXT_STEP = {
    SequenceStep.first: (SequenceStep.followup1, FOLLOWUP2_DAYS),
    SequenceStep.followup1: (SequenceStep.followup2, None),
    SequenceStep.followup2: (SequenceStep.stopped, None),
}


async def advance_followup(session, *, prev: Outreach, emit=_real_emit) -> Outreach | None:
    """Create + send the next sequence step for an unanswered outreach."""
    nxt, _ = _NEXT_STEP.get(prev.sequence_step, (SequenceStep.stopped, None))
    if nxt is SequenceStep.stopped:
        prev.sequence_step = SequenceStep.stopped
        prev.status = OutreachStatus.stopped
        prev.next_action_at = None
        return None

    body = f"Just following up on my note about the role. Still keen to connect.\n\n{prev.body or ''}"
    followup = Outreach(
        user_id=prev.user_id, application_id=prev.application_id, contact_id=prev.contact_id,
        sending_domain_id=prev.sending_domain_id, thread_id=prev.thread_id,
        sequence_step=nxt, status=OutreachStatus.queued,
        subject=f"Re: {prev.subject}" if prev.subject else "Following up", body=body,
    )
    session.add(followup)
    prev.next_action_at = None  # this one is handled; the new step owns the timer
    await session.flush()
    await send_outreach(session, outreach_id=followup.id, emit=emit)
    return followup

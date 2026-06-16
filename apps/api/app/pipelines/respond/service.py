"""Pipeline C orchestration: match -> classify -> dossier -> push to VA -> relay.

Inbound replies match to a job via the signed reply-address (primary), header
threading (fallback), or sender address (last resort). VA replies relayed from
WhatsApp go back out as threaded email — through the warm-up governor.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.enums import (
    DossierStatus,
    OutreachStatus,
    ReplyClassification,
    ReplyDirection,
    ThreadState,
)
from app.email import addressing
from app.email.governor import SendResult, governed_relay
from app.events import names
from app.events.bus import emit as _real_emit
from app.events.contracts import ReplyReceived
from app.integrations import bridge_client, resend
from app.llm import classify_reply
from app.models.application import Application
from app.models.contact import Contact
from app.models.dossier import Dossier
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.reply import Reply
from app.models.thread import Thread
from app.models.user import User
from app.repositories import applications as app_repo
from app.repositories import vas as vas_repo

log = structlog.get_logger(__name__)


async def match_thread(
    session, *, to_addr: str | None, in_reply_to: str | None, from_addr: str | None
) -> Thread | None:
    """3-tier match: signed tag -> header threading -> sender address."""
    # 1. Exact tagged reply-address.
    if to_addr:
        thread = (
            await session.execute(select(Thread).where(Thread.reply_address == to_addr))
        ).scalar_one_or_none()
        if thread is not None:
            return thread
        # 1b. Decode the signed tag -> job_id -> thread via its application.
        job_id = addressing.decode_reply_address(to_addr)
        if job_id is not None:
            thread = (
                await session.execute(
                    select(Thread)
                    .join(Application, Application.id == Thread.application_id)
                    .where(Application.job_id == job_id)
                    .order_by(Thread.created_at.desc())
                )
            ).scalars().first()
            if thread is not None:
                return thread

    # 2. Header threading.
    if in_reply_to:
        thread = (
            await session.execute(
                select(Thread).where(Thread.root_message_id == in_reply_to)
            )
        ).scalar_one_or_none()
        if thread is not None:
            return thread

    # 3. Sender address -> latest open thread for that contact.
    if from_addr:
        thread = (
            await session.execute(
                select(Thread)
                .join(Contact, Contact.id == Thread.contact_id)
                .where(Contact.email == from_addr, Thread.state != ThreadState.closed)
                .order_by(Thread.created_at.desc())
            )
        ).scalars().first()
        if thread is not None:
            return thread
    return None


async def ingest_inbound(
    session, *, to_addr: str | None, from_addr: str | None, subject: str | None,
    body: str | None, in_reply_to: str | None = None, message_id: str | None = None,
    emit=_real_emit,
) -> Reply | None:
    """Persist an inbound reply, stop the sequencer for its outreach, emit event."""
    thread = await match_thread(
        session, to_addr=to_addr, in_reply_to=in_reply_to, from_addr=from_addr
    )
    if thread is None:
        log.warning("respond.unmatched", to=to_addr, from_addr=from_addr)
        return None

    # Idempotency: ignore a duplicate message_id.
    if message_id:
        existing = (
            await session.execute(select(Reply).where(Reply.message_id == message_id))
        ).scalar_one_or_none()
        if existing is not None:
            return existing

    reply = Reply(
        user_id=thread.user_id, thread_id=thread.id, direction=ReplyDirection.inbound,
        from_addr=from_addr, to_addr=to_addr, message_id=message_id,
        in_reply_to=in_reply_to, subject=subject, body=body,
        received_at=datetime.now(timezone.utc),
    )
    session.add(reply)
    thread.state = ThreadState.awaiting_va
    thread.last_inbound_at = reply.received_at

    # Stop the follow-up sequencer for this conversation.
    for outreach in (
        await session.execute(select(Outreach).where(Outreach.thread_id == thread.id))
    ).scalars().all():
        if outreach.status == OutreachStatus.sent:
            outreach.status = OutreachStatus.replied
            outreach.next_action_at = None

    await session.flush()
    emit(
        names.REPLY_RECEIVED,
        ReplyReceived(user_id=reply.user_id, reply_id=reply.id, thread_id=thread.id),
    )
    log.info("respond.ingested", reply_id=str(reply.id), thread=str(thread.id))
    return reply


async def process_reply(session, *, reply_id: UUID, emit=_real_emit) -> Dossier | None:
    """Classify, assemble a dossier, resolve + push to the assigned VA on WhatsApp."""
    reply = await session.get(Reply, reply_id)
    thread = await session.get(Thread, reply.thread_id)
    application = await session.get(Application, thread.application_id)
    job = await session.get(Job, application.job_id)
    hunter = await session.get(User, thread.user_id)
    contact = await session.get(Contact, thread.contact_id)

    classification, suggested = await classify_reply.classify(reply.body or "")
    reply.classification = classification
    reply.suggested_draft = suggested

    va = await vas_repo.resolve_assignee(session, user_id=thread.user_id, track=job.track)

    summary = (
        f"Reply on {job.company} — {job.role_title or job.title} "
        f"(hunter: {hunter.name}). {classification.value.upper()} reply from "
        f"{contact.full_name or reply.from_addr}."
    )
    dossier = Dossier(
        user_id=thread.user_id, thread_id=thread.id, reply_id=reply.id,
        va_id=va.id if va else None,
        summary=summary,
        # Routine -> auto-draft attached; substantive -> context only (VA writes).
        suggested_reply=suggested if classification is ReplyClassification.routine else None,
        context={
            "company": job.company, "role": job.role_title or job.title,
            "owning_hunter": hunter.name, "applied_at": str(application.submitted_at),
            "cv_id": str(application.generated_cv_id), "from": reply.from_addr,
            "reply_body": reply.body, "classification": classification.value,
        },
        status=DossierStatus.pushed, pushed_at=datetime.now(timezone.utc),
    )
    session.add(dossier)
    await session.flush()

    if va is not None:
        ref = await bridge_client.push_to_va(
            va_jid=va.whatsapp_jid, dossier_id=str(dossier.id),
            text=f"{summary}\n\n{reply.body or ''}"
            + (f"\n\nSuggested reply:\n{suggested}" if suggested else ""),
        )
        dossier.bridge_message_ref = ref

    app_repo.record_event(
        session, application=application, kind="reply_received",
        detail={"classification": classification.value, "from": reply.from_addr},
    )
    log.info("respond.dossier", dossier_id=str(dossier.id), va=bool(va))
    return dossier


async def relay_va_reply(
    session, *, va_jid: str, in_reply_to_ref: str, text: str, emit=_real_emit
) -> SendResult:
    """A VA replied in WhatsApp -> relay as a threaded email through the governor."""
    dossier = (
        await session.execute(
            select(Dossier).where(Dossier.bridge_message_ref == in_reply_to_ref)
        )
    ).scalar_one_or_none()
    if dossier is None:
        log.warning("respond.relay.no_dossier", ref=in_reply_to_ref)
        return SendResult.deferred

    thread = await session.get(Thread, dossier.thread_id)
    inbound = await session.get(Reply, dossier.reply_id)
    contact = await session.get(Contact, thread.contact_id)
    hunter = await session.get(User, thread.user_id)

    async def send_fn(domain):
        sender = f"{hunter.name} <{domain.track.value}@{domain.domain}>"
        headers = {"In-Reply-To": inbound.message_id} if inbound.message_id else {}
        if inbound.message_id:
            headers["References"] = inbound.message_id
        return await resend.send_email(
            sender=sender, to=contact.email,
            subject=f"Re: {inbound.subject or 'your message'}", body=text,
            reply_to=thread.reply_address, headers=headers,
        )

    result, message_id = await governed_relay(
        session, user_id=thread.user_id, sending_domain_id=thread.sending_domain_id,
        send_fn=send_fn,
    )
    if result is SendResult.sent:
        session.add(Reply(
            user_id=thread.user_id, thread_id=thread.id, direction=ReplyDirection.outbound,
            from_addr=thread.reply_address, to_addr=contact.email,
            message_id=message_id, in_reply_to=inbound.message_id,
            subject=f"Re: {inbound.subject or ''}", body=text,
            received_at=datetime.now(timezone.utc),
        ))
        dossier.status = DossierStatus.relayed
        thread.state = ThreadState.open
        thread.last_outbound_at = datetime.now(timezone.utc)
    await session.flush()
    log.info("respond.relayed", dossier_id=str(dossier.id), result=result.value)
    return result

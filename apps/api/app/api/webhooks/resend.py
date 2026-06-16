"""Resend webhooks: inbound mail -> Pipeline C; delivery events -> domain health."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.db import get_session
from app.email import health
from app.integrations import resend as resend_int
from app.pipelines.respond import service as respond_service

router = APIRouter(prefix="/resend")


def _domain_of(addr: str | None) -> str | None:
    return addr.split("@", 1)[1] if addr and "@" in addr else None


@router.post("/inbound")
async def inbound(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    """Parsed inbound email -> match to a thread, persist, emit reply.received."""
    raw = await request.body()
    if not resend_int.verify_webhook(request.headers.get("X-Resend-Signature"), raw):
        raise AuthError("Invalid webhook signature")
    data = json.loads(raw or b"{}")
    # Accept either a flat shape or Resend's {type, data:{...}} envelope.
    payload = data.get("data", data)
    reply = await respond_service.ingest_inbound(
        session,
        to_addr=payload.get("to") if isinstance(payload.get("to"), str)
        else (payload.get("to") or [None])[0],
        from_addr=payload.get("from"),
        subject=payload.get("subject"),
        body=payload.get("text") or payload.get("body"),
        in_reply_to=payload.get("in_reply_to") or (payload.get("headers") or {}).get("in-reply-to"),
        message_id=payload.get("message_id") or (payload.get("headers") or {}).get("message-id"),
    )
    return {"matched": reply is not None}


@router.post("/events")
async def events(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    """Delivery events (bounce/complaint) -> per-domain health + auto-pause."""
    raw = await request.body()
    if not resend_int.verify_webhook(request.headers.get("X-Resend-Signature"), raw):
        raise AuthError("Invalid webhook signature")
    data = json.loads(raw or b"{}")
    event_type = data.get("type", "")
    payload = data.get("data", {})
    sender = payload.get("from") or (payload.get("from_address"))
    domain_name = _domain_of(sender)
    if domain_name:
        await health.ingest_event(session, domain_name=domain_name, event_type=event_type)
    return {"ok": True}

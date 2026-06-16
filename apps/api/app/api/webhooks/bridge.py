"""Bridge webhook: a VA's WhatsApp reply -> relay as a threaded email."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthError
from app.db import get_session
from app.integrations import bridge_client
from app.pipelines.respond import service as respond_service

router = APIRouter(prefix="/bridge")


@router.post("/reply")
async def reply(request: Request, session: AsyncSession = Depends(get_session)) -> dict:
    """`{va_jid, in_reply_to_ref, text, ts}` (HMAC-signed) -> governed relay."""
    raw = await request.body()
    if not bridge_client.verify_bridge_signature(request.headers.get("X-Bridge-Signature"), raw):
        raise AuthError("Invalid bridge signature")
    data = json.loads(raw or b"{}")
    result = await respond_service.relay_va_reply(
        session,
        va_jid=data.get("va_jid", ""),
        in_reply_to_ref=data.get("in_reply_to_ref", ""),
        text=data.get("text", ""),
    )
    return {"result": result.value}

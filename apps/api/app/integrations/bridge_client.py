"""Client for the Go whatsmeow bridge. FastAPI -> bridge `POST /push`.

Fake mode captures pushes in-process (no bridge needed). Real mode signs the
body with the shared HMAC secret the bridge verifies.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx

from app.config import settings

# Captured pushes in fake mode (test introspection).
PUSH_LOG: list[dict] = []


def _sign(raw: bytes) -> str:
    return hmac.new(settings.bridge_hmac_secret.encode(), raw, hashlib.sha256).hexdigest()


async def push_to_va(*, va_jid: str, dossier_id: str, text: str) -> str:
    """Push dossier text to a VA's WhatsApp; return the bridge_message_ref."""
    if settings.use_fake_integrations:
        ref = f"br-{len(PUSH_LOG)}"
        PUSH_LOG.append({"va_jid": va_jid, "dossier_id": dossier_id, "text": text, "ref": ref})
        return ref

    body = {"va_jid": va_jid, "dossier_id": dossier_id, "text": text}
    raw = json.dumps(body).encode()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{settings.bridge_base_url}/push",
            content=raw,
            headers={"Content-Type": "application/json", "X-Bridge-Signature": _sign(raw)},
        )
        resp.raise_for_status()
        return resp.json().get("bridge_message_ref", "")


def verify_bridge_signature(signature: str | None, raw_body: bytes) -> bool:
    """Verify an inbound VA-reply callback from the bridge."""
    if settings.use_fake_integrations:
        return True
    if not signature:
        return False
    return hmac.compare_digest(signature, _sign(raw_body))

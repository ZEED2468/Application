"""Resend email send + inbound/event webhook signature verification.

Fake mode returns a deterministic message id and records the send so tests can
assert on it. No module calls this directly — sends route through the warm-up
governor's `send_fn` (see app/email/sender.py).
"""

from __future__ import annotations

import hashlib
import hmac

from app.config import settings

# Records of sent mail in fake mode (test introspection).
SENT_LOG: list[dict] = []


async def send_email(
    *, sender: str, to: str, subject: str, body: str,
    reply_to: str | None = None, headers: dict | None = None,
) -> str:
    """Send and return the provider message id."""
    if settings.use_fake_integrations or not settings.resend_api_key:
        idx = len(SENT_LOG)
        message_id = f"<fake-{idx}@resend.local>"
        SENT_LOG.append(
            {"from": sender, "to": to, "subject": subject, "body": body,
             "reply_to": reply_to, "headers": headers or {}, "message_id": message_id}
        )
        return message_id

    import resend

    resend.api_key = settings.resend_api_key
    params: dict = {"from": sender, "to": [to], "subject": subject, "text": body}
    if reply_to:
        params["reply_to"] = reply_to
    if headers:
        params["headers"] = headers
    result = resend.Emails.send(params)
    return result.get("id", "")


def verify_webhook(signature: str | None, raw_body: bytes) -> bool:
    """HMAC-SHA256 verification of a Resend webhook (Svix-style secret)."""
    if settings.use_fake_integrations:
        return True
    if not signature:
        return False
    expected = hmac.new(
        settings.resend_webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected)

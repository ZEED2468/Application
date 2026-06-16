"""Builds the `send_fn(outreach, domain)` the warm-up governor invokes.

This is the ONLY place that talks to the email provider for an outbound message.
It sets the From `<track>@<domain>`, the tagged Reply-To, and threading headers,
then calls Resend and returns the provider message id.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.email import addressing
from app.integrations import resend
from app.models.outreach import Outreach
from app.models.sending_domain import SendingDomain


def make_send_fn(
    *, to_email: str, candidate_name: str, job_id, in_reply_to: str | None = None,
    references: str | None = None,
) -> Callable[[Outreach, SendingDomain], Awaitable[str]]:
    """Return a send_fn closure carrying recipient + threading context."""

    async def send_fn(outreach: Outreach, domain: SendingDomain) -> str:
        sender = f"{candidate_name} <{domain.track.value}@{domain.domain}>"
        reply_to = addressing.encode_reply_address(job_id, domain.domain)
        outreach.reply_address = reply_to
        headers: dict = {}
        if in_reply_to:
            headers["In-Reply-To"] = in_reply_to
            headers["References"] = references or in_reply_to
        return await resend.send_email(
            sender=sender, to=to_email, subject=outreach.subject or "",
            body=outreach.body or "", reply_to=reply_to, headers=headers,
        )

    return send_fn

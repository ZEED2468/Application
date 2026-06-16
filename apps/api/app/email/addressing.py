"""Tagged reply-address encode/decode: apply+<token>@<domain>.

The token is an HMAC-signed short form of the job id so inbound replies match
header-independently and tags can't be spoofed.
"""

from __future__ import annotations

import base64
import hmac
from hashlib import sha256
from uuid import UUID

from app.config import settings

_PREFIX = "apply"


def _sig(job_hex: str) -> str:
    mac = hmac.new(settings.bridge_hmac_secret.encode(), job_hex.encode(), sha256).digest()
    return base64.urlsafe_b64encode(mac[:6]).decode().rstrip("=")


def encode_reply_address(job_id: UUID, domain: str) -> str:
    job_hex = job_id.hex
    token = f"{job_hex}.{_sig(job_hex)}"
    return f"{_PREFIX}+{token}@{domain}"


def decode_reply_address(address: str) -> UUID | None:
    """Return the job id if the tag is present and the signature verifies."""
    try:
        local = address.split("@", 1)[0]
        if "+" not in local:
            return None
        _, token = local.split("+", 1)
        job_hex, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sig(job_hex)):
            return None
        return UUID(hex=job_hex)
    except (ValueError, IndexError):
        return None

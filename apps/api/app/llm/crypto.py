"""Encryption for per-user LLM API keys at rest (R1).

Uses Fernet (AES-128-CBC + HMAC) with a key derived from `CREDENTIAL_ENC_KEY`
(falling back to `JWT_SECRET` for dev). Plaintext keys are never returned to the
client — `mask()` produces a safe display form.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    secret = settings.credential_enc_key or settings.jwt_secret
    # Derive a stable 32-byte urlsafe key from whatever secret is configured.
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def mask(plaintext: str) -> str:
    """A safe, non-reversible display form: keep the last 4 chars."""
    s = plaintext or ""
    if len(s) <= 4:
        return "••••"
    return "••••" + s[-4:]

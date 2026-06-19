"""Password hashing (argon2) and JWT access/refresh token helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import settings
from app.core.enums import PrincipalType

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(
    *, subject_id: UUID, principal: PrincipalType, role: str | None = None,
    track_scope: list[str] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(subject_id),
        "type": principal.value,
        "role": role,
        "track_scope": track_scope or [],
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Store only the hash."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# Unambiguous alphabet: A-Z + 2-9, dropping 0/O/1/I to keep codes easy to read/type.
_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
INVITE_KEY_LENGTH = 6


def generate_invite_key() -> tuple[str, str]:
    """Return (code, sha256_hash) for a 6-char invite key. Store only the hash.

    Reuses `hash_refresh_token` so verification is a plain hash lookup. The short
    code is safe because lookups are scoped by email and the invite is single-use
    and expiring.
    """
    code = "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(INVITE_KEY_LENGTH))
    return code, hash_refresh_token(code)

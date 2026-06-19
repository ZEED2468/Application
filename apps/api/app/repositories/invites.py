"""Invite data access + signup-eligibility guards.

All lookups are email-scoped. Invite keys are stored hashed (never the raw code),
mirroring the refresh-token pattern.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InviteKind, InviteStatus, Track
from app.core.errors import ConflictError
from app.models.invite import Invite
from app.models.user import User
from app.models.va import Va
from app.security import generate_invite_key

INVITE_TTL_DAYS = 7


def normalize_email(email: str) -> str:
    return email.strip().lower()


def phone_to_jid(value: str) -> str:
    """Turn a phone number (or an already-formed JID) into a whatsmeow JID."""
    value = value.strip()
    if "@" in value:
        return value
    digits = re.sub(r"\D", "", value)
    return f"{digits}@s.whatsapp.net"


async def _email_taken(session: AsyncSession, email: str) -> bool:
    user = (await session.execute(select(User.id).where(User.email == email))).first()
    if user:
        return True
    va = (await session.execute(select(Va.id).where(Va.email == email))).first()
    return va is not None


async def create(
    session: AsyncSession,
    *,
    email: str,
    kind: InviteKind,
    invited_by_user_id: UUID,
    va_name: str | None = None,
    va_whatsapp_jid: str | None = None,
    track: Track | None = None,
    platform_id: UUID | None = None,
) -> tuple[Invite, str]:
    """Create a pending invite. Returns (invite, raw_code). The raw code is shown
    once to the inviter and never persisted. Raises ConflictError if the email is
    already an account or already has a pending invite."""
    email = normalize_email(email)
    if await _email_taken(session, email):
        raise ConflictError("That email already has an account.")
    existing = (
        await session.execute(
            select(Invite).where(
                Invite.email == email, Invite.status == InviteStatus.pending
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("A pending invite already exists for that email.")

    code, key_hash = generate_invite_key()
    invite = Invite(
        email=email,
        key_hash=key_hash,
        kind=kind,
        invited_by_user_id=invited_by_user_id,
        va_name=va_name,
        va_whatsapp_jid=va_whatsapp_jid,
        track=track,
        platform_id=platform_id,
        status=InviteStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    session.add(invite)
    await session.flush()
    return invite, code


async def get_redeemable(
    session: AsyncSession, *, email: str, key_hash: str
) -> Invite | None:
    """A pending, unexpired invite matching this email + key hash, else None."""
    invite = (
        await session.execute(
            select(Invite).where(
                Invite.email == normalize_email(email), Invite.key_hash == key_hash
            )
        )
    ).scalar_one_or_none()
    if invite is None or invite.status is not InviteStatus.pending:
        return None
    # SQLite returns naive datetimes; treat a naive expiry as UTC before comparing.
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return invite


async def list_created_by(
    session: AsyncSession, *, user_id: UUID, kind: InviteKind | None = None
) -> list[Invite]:
    stmt = select(Invite).where(Invite.invited_by_user_id == user_id)
    if kind is not None:
        stmt = stmt.where(Invite.kind == kind)
    stmt = stmt.order_by(Invite.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_owned(
    session: AsyncSession, *, invite_id: UUID, user_id: UUID
) -> Invite | None:
    return (
        await session.execute(
            select(Invite).where(
                Invite.id == invite_id, Invite.invited_by_user_id == user_id
            )
        )
    ).scalar_one_or_none()

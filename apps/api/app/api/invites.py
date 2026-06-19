"""Invite management — admins invite hunters; hunters invite their VAs.

The raw 6-char key is returned ONCE at creation (inside a copyable signup link);
thereafter only its hash is stored. `current_user` gates VA invites, which also
means a VA principal can never reach these routes (no VA-invites-a-VA).
"""

from __future__ import annotations

from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InviteKind, InviteStatus
from app.core.errors import NotFoundError
from app.db import get_session
from app.deps import current_user, require_admin
from app.models.user import User
from app.repositories import invites as invites_repo
from app.schemas.auth import (
    HunterInviteRequest,
    InviteCreatedResponse,
    InviteOut,
    VaInviteRequest,
)

router = APIRouter(prefix="/invites", tags=["invites"])


def _signup_link(email: str, key: str) -> str:
    """Relative signup link; the frontend prepends its own origin when sharing."""
    return f"/signup?{urlencode({'email': email, 'key': key})}"


def _created(invite, key: str) -> InviteCreatedResponse:
    return InviteCreatedResponse(
        id=invite.id, email=invite.email, kind=invite.kind, status=invite.status,
        track=invite.track, va_name=invite.va_name, expires_at=invite.expires_at,
        created_at=invite.created_at, key=key, signup_link=_signup_link(invite.email, key),
    )


@router.post("/hunter", response_model=InviteCreatedResponse)
async def invite_hunter(
    body: HunterInviteRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> InviteCreatedResponse:
    invite, key = await invites_repo.create(
        session, email=str(body.email), kind=InviteKind.hunter, invited_by_user_id=admin.id
    )
    return _created(invite, key)


@router.post("/va", response_model=InviteCreatedResponse)
async def invite_va(
    body: VaInviteRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> InviteCreatedResponse:
    invite, key = await invites_repo.create(
        session, email=str(body.email), kind=InviteKind.va, invited_by_user_id=user.id,
        va_name=body.va_name, va_whatsapp_jid=invites_repo.phone_to_jid(body.whatsapp),
        track=body.track,
    )
    return _created(invite, key)


@router.get("", response_model=list[InviteOut])
async def list_invites(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[InviteOut]:
    rows = await invites_repo.list_created_by(session, user_id=user.id)
    return [
        InviteOut(
            id=i.id, email=i.email, kind=i.kind, status=i.status, track=i.track,
            va_name=i.va_name, expires_at=i.expires_at, created_at=i.created_at,
        )
        for i in rows
    ]


@router.delete("/{invite_id}")
async def revoke_invite(
    invite_id: UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    invite = await invites_repo.get_owned(session, invite_id=invite_id, user_id=user.id)
    if invite is None:
        raise NotFoundError("Invite not found")
    if invite.status is InviteStatus.pending:
        invite.status = InviteStatus.revoked
    await session.flush()
    return {"status": invite.status.value}

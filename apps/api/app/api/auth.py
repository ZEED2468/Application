"""Auth endpoints: login / refresh / me / logout.

Matches the reference frontend: httpOnly access_token + rotating refresh cookie.
Both hunters (User) and VAs authenticate here, discriminated by principal type.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import InviteKind, InviteStatus, PrincipalType, UserRole
from app.core.errors import AuthError
from app.db import get_session
from app.deps import ACCESS_COOKIE, Principal, current_principal
from app.models.invite import Invite
from app.models.platform import Platform
from app.models.user import RefreshToken, User
from app.models.va import Va
from app.models.va_assignment import VaAssignment
from app.repositories import invites as invites_repo
from app.schemas.auth import LoginRequest, MeResponse, RegisterRequest
from app.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _cookie_attrs() -> dict:
    samesite = settings.cookie_samesite.lower()
    # Browsers reject SameSite=None unless Secure is also set.
    secure = settings.cookie_secure or samesite == "none"
    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "domain": settings.cookie_domain,
    }


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    common = _cookie_attrs()
    response.set_cookie(
        ACCESS_COOKIE, access, max_age=settings.access_token_ttl_minutes * 60, **common
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh, max_age=settings.refresh_token_ttl_days * 86400,
        path="/api/auth", **common,
    )


async def _issue_session(
    response: Response, session: AsyncSession, *, subject_id, principal: PrincipalType,
    role: str | None, track_scope: list[str],
) -> None:
    access = create_access_token(
        subject_id=subject_id, principal=principal, role=role, track_scope=track_scope
    )
    raw, token_hash = generate_refresh_token()
    session.add(
        RefreshToken(
            subject_id=subject_id,
            subject_type=principal.value,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    _set_auth_cookies(response, access, raw)


@router.post("/login", response_model=MeResponse)
async def login(
    body: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)
) -> MeResponse:
    # Try hunter first, then VA — single login surface, two principal types.
    user = (
        await session.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if user and verify_password(body.password, user.password_hash):
        await _issue_session(
            response, session, subject_id=user.id, principal=PrincipalType.user,
            role=user.role.value, track_scope=[],
        )
        return await _user_me(session, user)

    va = (
        await session.execute(select(Va).where(Va.email == body.email))
    ).scalar_one_or_none()
    if va and verify_password(body.password, va.password_hash):
        await _issue_session(
            response, session, subject_id=va.id, principal=PrincipalType.va,
            role="va", track_scope=[],
        )
        return MeResponse(id=va.id, type="va", email=va.email, name=va.name, role="va")

    raise AuthError("Invalid credentials")


@router.post("/register", response_model=MeResponse)
async def register(
    body: RegisterRequest, response: Response, session: AsyncSession = Depends(get_session)
) -> MeResponse:
    """Redeem an invite key to create an account, then auto-login.

    The invite (created by an admin for a hunter, or by a hunter for their VA)
    carries the account kind + any VA context. The email+key must match a pending,
    unexpired invite — otherwise no account is created.
    """
    key = body.key.strip().upper()
    invite = await invites_repo.get_redeemable(
        session, email=str(body.email), key_hash=hash_refresh_token(key)
    )
    if invite is None:
        raise AuthError("Invalid or expired invite. Check the email and key.")

    email = invites_repo.normalize_email(str(body.email))
    password_hash = hash_password(body.password)

    if invite.kind is InviteKind.va:
        va = await _create_va(session, invite, email, password_hash)
        invite.status = InviteStatus.accepted
        invite.accepted_at = datetime.now(timezone.utc)
        await _issue_session(
            response, session, subject_id=va.id, principal=PrincipalType.va,
            role="va", track_scope=[],
        )
        return MeResponse(id=va.id, type="va", email=email, name=va.name, role="va")

    display = (body.name or "").strip() or email.split("@", 1)[0] or "User"

    # hunter or admin -> a User; an admin carries the invite's platform.
    new_role = UserRole.admin if invite.kind is InviteKind.admin else UserRole.hunter
    platform_id = invite.platform_id if invite.kind is InviteKind.admin else None
    user = await _create_user(
        session, email, display, password_hash, role=new_role, platform_id=platform_id
    )
    invite.status = InviteStatus.accepted
    invite.accepted_at = datetime.now(timezone.utc)
    await _issue_session(
        response, session, subject_id=user.id, principal=PrincipalType.user,
        role=new_role.value, track_scope=[],
    )
    return await _user_me(session, user)


async def _create_user(session, email, name, password_hash, *, role: UserRole, platform_id):
    user = User(email=email, name=name, role=role, password_hash=password_hash,
                platform_id=platform_id)
    session.add(user)
    await session.flush()
    return user


async def _create_va(
    session, invite: Invite, email, password_hash,
) -> Va:
    display = email.split("@", 1)[0] or "VA"
    va = Va(
        name=display,
        email=email,
        password_hash=password_hash,
        pin_hash=None,
        whatsapp_jid=invite.va_whatsapp_jid or f"{email}@s.whatsapp.net",
    )
    session.add(va)
    await session.flush()
    # Bind the VA to the inviting hunter (so they share that dashboard).
    session.add(VaAssignment(va_id=va.id, user_id=invite.invited_by_user_id, track=invite.track))
    return va


async def _user_me(session, user: User) -> MeResponse:
    """MeResponse for a User, resolving the attached platform (admins only)."""
    platform_name = None
    if user.platform_id is not None:
        platform = await session.get(Platform, user.platform_id)
        platform_name = platform.name if platform else None
    return MeResponse(
        id=user.id, type="user", email=user.email, name=user.name,
        role=user.role.value, platform_id=user.platform_id, platform_name=platform_name,
    )


@router.post("/refresh")
async def refresh(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> dict:
    if not refresh_token:
        raise AuthError("No refresh token")
    token_hash = hash_refresh_token(refresh_token)
    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None or row.revoked_at is not None or row.expires_at < now:
        raise AuthError("Invalid refresh token")

    # Rotate: revoke old, issue new.
    row.revoked_at = now
    principal = PrincipalType(row.subject_type)
    role = None
    if principal is PrincipalType.user:
        user = await session.get(User, row.subject_id)
        role = user.role.value if user else None
    else:
        role = "va"
    await _issue_session(
        response, session, subject_id=row.subject_id, principal=principal,
        role=role, track_scope=[],
    )
    return {"status": "refreshed"}


@router.get("/me", response_model=MeResponse)
async def me(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    if principal.type is PrincipalType.user:
        user = await session.get(User, principal.id)
        if not user:
            raise AuthError("Not found")
        return await _user_me(session, user)
    va = await session.get(Va, principal.id)
    if not va:
        raise AuthError("Not found")
    return MeResponse(id=va.id, type="va", email=va.email, name=va.name, role="va")


@router.post("/logout")
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
) -> dict:
    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)
        row = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
        if row and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
    attrs = _cookie_attrs()
    response.delete_cookie(ACCESS_COOKIE, samesite=attrs["samesite"], secure=attrs["secure"],
                           domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth", samesite=attrs["samesite"],
                           secure=attrs["secure"], domain=settings.cookie_domain)
    return {"status": "logged_out"}

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
from app.core.enums import PrincipalType
from app.core.errors import AuthError
from app.db import get_session
from app.deps import ACCESS_COOKIE, Principal, current_principal
from app.models.user import RefreshToken, User
from app.models.va import Va
from app.schemas.auth import LoginRequest, MeResponse
from app.security import (
    create_access_token,
    generate_refresh_token,
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
        return MeResponse(
            id=user.id, type="user", email=user.email, name=user.name, role=user.role.value
        )

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
        return MeResponse(
            id=user.id, type="user", email=user.email, name=user.name, role=user.role.value
        )
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

"""FastAPI dependencies: DB session + authenticated principal resolution."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PrincipalType, UserRole
from app.core.errors import AuthError, ForbiddenError
from app.db import get_session
from app.models.user import User
from app.models.va import Va
from app.security import decode_access_token

ACCESS_COOKIE = "access_token"


@dataclass
class Principal:
    id: UUID
    type: PrincipalType
    role: str | None
    track_scope: list[str]


async def current_principal(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
) -> Principal:
    if not access_token:
        raise AuthError("Not authenticated")
    try:
        claims = decode_access_token(access_token)
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid or expired token") from exc
    return Principal(
        id=UUID(claims["sub"]),
        type=PrincipalType(claims["type"]),
        role=claims.get("role"),
        track_scope=claims.get("track_scope", []),
    )


async def current_user(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> User:
    if principal.type is not PrincipalType.user:
        raise ForbiddenError("Hunter account required")
    user = await session.get(User, principal.id)
    if user is None or not user.is_active:
        raise AuthError("User not found")
    return user


async def current_va(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> Va:
    if principal.type is not PrincipalType.va:
        raise ForbiddenError("VA account required")
    va = await session.get(Va, principal.id)
    if va is None or not va.is_active:
        raise AuthError("VA not found")
    return va


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role is not UserRole.admin:
        raise ForbiddenError("Admin role required")
    return user

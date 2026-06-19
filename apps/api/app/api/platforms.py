"""Platforms + admin accounts. Admin is the single top-level (super) admin role, so
every route here is gated by `require_admin`; a platform is a label attached to an
admin, not a data partition."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.errors import ConflictError, NotFoundError
from app.core.ids import new_id
from app.db import get_session
from app.deps import require_admin
from app.models.platform import Platform
from app.models.user import User
from app.schemas.platforms import AdminOut, PlatformCreate, PlatformOut, PlatformUpdate

router = APIRouter(tags=["admin"])


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return base or "platform"


async def _unique_slug(session: AsyncSession, name: str) -> str:
    base = _slugify(name)
    exists = (
        await session.execute(select(Platform.id).where(Platform.slug == base))
    ).first()
    return base if not exists else f"{base}-{new_id().hex[:6]}"


@router.get("/platforms", response_model=list[PlatformOut])
async def list_platforms(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[Platform]:
    rows = (
        await session.execute(select(Platform).order_by(Platform.created_at.desc()))
    ).scalars().all()
    return list(rows)


@router.post("/platforms", response_model=PlatformOut)
async def create_platform(
    body: PlatformCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Platform:
    platform = Platform(name=body.name.strip(), slug=await _unique_slug(session, body.name))
    session.add(platform)
    await session.flush()
    return platform


@router.patch("/platforms/{platform_id}", response_model=PlatformOut)
async def update_platform(
    platform_id: UUID,
    body: PlatformUpdate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Platform:
    platform = await session.get(Platform, platform_id)
    if platform is None:
        raise NotFoundError("Platform not found")
    if body.name is not None:
        platform.name = body.name.strip()
    if body.is_active is not None:
        platform.is_active = body.is_active
    await session.flush()
    return platform


@router.get("/admins", response_model=list[AdminOut])
async def list_admins(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> list[AdminOut]:
    admins = (
        await session.execute(
            select(User).where(User.role == UserRole.admin).order_by(User.created_at.desc())
        )
    ).scalars().all()
    # name platforms in one pass
    platforms = {
        p.id: p.name
        for p in (await session.execute(select(Platform))).scalars().all()
    }
    return [
        AdminOut(
            id=a.id, name=a.name, email=a.email, role=a.role.value, is_active=a.is_active,
            platform_id=a.platform_id, platform_name=platforms.get(a.platform_id),
        )
        for a in admins
    ]

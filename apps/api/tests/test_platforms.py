"""Platforms + admin-invite flow, end-to-end against the ASGI app (https client)."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import UserRole
from app.db import get_session
from app.main import app
from app.models import Base
from app.models.user import User
from app.security import hash_password

ADMIN = {"email": "admin@example.com", "password": "s3cretpw"}


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(User(email=ADMIN["email"], password_hash=hash_password(ADMIN["password"]),
                   name="Admin", role=UserRole.admin))
        await s.commit()

    async def _override():
        async with maker() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r


async def _make_platform(client, name="Acme"):
    r = await client.post("/api/platforms", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_admin_creates_platform_and_invites_admin(client):
    await _login(client, **ADMIN)
    platform = await _make_platform(client, "Acme")
    assert platform["slug"] == "acme"

    # platform shows up in the list
    plats = await client.get("/api/platforms")
    assert plats.status_code == 200
    assert any(p["id"] == platform["id"] for p in plats.json())

    # invite an admin attached to the platform
    inv = await client.post(
        "/api/invites/admin", json={"email": "boss@example.com", "platform_id": platform["id"]}
    )
    assert inv.status_code == 200, inv.text

    reg = await client.post("/api/auth/register", json={
        "email": "boss@example.com", "name": "Boss", "password": "newpassw0rd", "key": inv.json()["key"],
    })
    assert reg.status_code == 200, reg.text
    me = reg.json()
    assert me["role"] == "admin"
    assert me["platform_id"] == platform["id"]
    assert me["platform_name"] == "Acme"

    # the new admin can log in and is listed under /admins with their platform
    await _login(client, "boss@example.com", "newpassw0rd")
    admins = await client.get("/api/admins")
    assert admins.status_code == 200
    boss = next(a for a in admins.json() if a["email"] == "boss@example.com")
    assert boss["platform_name"] == "Acme"


@pytest.mark.asyncio
async def test_invite_admin_rejects_unknown_platform(client):
    await _login(client, **ADMIN)
    bad = await client.post(
        "/api/invites/admin",
        json={"email": "x@example.com", "platform_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert bad.status_code == 409


@pytest.mark.asyncio
async def test_hunter_cannot_touch_admin_surface(client):
    # admin invites a hunter, who registers (cookie becomes the hunter)
    await _login(client, **ADMIN)
    inv = await client.post("/api/invites/hunter", json={"email": "hunter@example.com"})
    reg = await client.post("/api/auth/register", json={
        "email": "hunter@example.com", "name": "Hunter", "password": "newpassw0rd", "key": inv.json()["key"],
    })
    assert reg.status_code == 200
    assert reg.json()["platform_id"] is None  # hunters carry no platform

    assert (await client.get("/api/platforms")).status_code == 403
    assert (await client.post("/api/platforms", json={"name": "X"})).status_code == 403
    assert (await client.get("/api/admins")).status_code == 403
    assert (await client.post("/api/invites/admin",
            json={"email": "y@e.com", "platform_id": str(UUID(int=0))})).status_code == 403


@pytest.mark.asyncio
async def test_deactivate_platform_blocks_invites(client):
    await _login(client, **ADMIN)
    platform = await _make_platform(client, "Beta")
    patch = await client.patch(f"/api/platforms/{platform['id']}", json={"is_active": False})
    assert patch.status_code == 200 and patch.json()["is_active"] is False
    blocked = await client.post(
        "/api/invites/admin", json={"email": "z@example.com", "platform_id": platform["id"]}
    )
    assert blocked.status_code == 409  # inactive platform

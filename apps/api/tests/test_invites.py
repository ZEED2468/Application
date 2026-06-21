"""Invite-gated signup + VA permission boundary, end-to-end against the ASGI app."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import InviteStatus, JobSourceName, JobStatus, Origin, Track, UserRole
from app.db import get_session
from app.main import app
from app.models import Base
from app.models.invite import Invite
from app.models.job import Job
from app.models.user import User
from app.models.va import Va
from app.models.va_assignment import VaAssignment
from app.security import hash_password

ADMIN = {"email": "admin@example.com", "password": "s3cretpw"}


@pytest_asyncio.fixture
async def ctx():
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
    # https so the app's cookies (Secure when COOKIE_SAMESITE=none) are sent back.
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c, maker
    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client, email, password):
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r


async def _invite_hunter(client, email):
    r = await client.post("/api/invites/hunter", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()


async def _register(client, *, email, name=None, key, password="newpassw0rd"):
    payload = {"email": email, "key": key, "password": password}
    if name is not None:
        payload["name"] = name
    return await client.post("/api/auth/register", json=payload)


async def _make_hunter(client, email="hunter@example.com"):
    """admin -> invite hunter -> register. Leaves the client logged in AS the hunter."""
    await _login(client, **ADMIN)
    inv = await _invite_hunter(client, email)
    reg = await _register(client, email=email, name="New Hunter", key=inv["key"])
    assert reg.status_code == 200, reg.text
    return UUID(reg.json()["id"])  # cookie now = hunter


async def _make_va(client, email="va@example.com", *, password="newpassw0rd"):
    """hunter (current cookie) -> invite VA -> register. Leaves the client logged in AS the VA."""
    inv = await client.post(
        "/api/invites/va",
        json={"email": email, "whatsapp": "+2348012345678"},
    )
    assert inv.status_code == 200, inv.text
    key = inv.json()["key"]
    reg = await _register(client, email=email, key=key, password=password)
    assert reg.status_code == 200, reg.text
    return UUID(reg.json()["id"]), key, password  # cookie now = va


# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_admin_invites_hunter_then_registers_and_logs_in(ctx):
    client, _ = ctx
    hunter_id = await _make_hunter(client)
    me = await client.get("/api/auth/me")
    assert me.json()["type"] == "user" and me.json()["role"] == "hunter"
    # fresh login works
    out = await client.post("/api/auth/login",
                            json={"email": "hunter@example.com", "password": "newpassw0rd"})
    assert out.status_code == 200
    assert UUID(out.json()["id"]) == hunter_id


@pytest.mark.asyncio
async def test_register_rejects_bad_key_and_wrong_email(ctx):
    client, _ = ctx
    await _login(client, **ADMIN)
    inv = await _invite_hunter(client, "h2@example.com")
    assert (await _register(client, email="h2@example.com", name="X", key="ZZZZZZ")).status_code == 401
    assert (await _register(client, email="other@example.com", name="X", key=inv["key"])).status_code == 401


@pytest.mark.asyncio
async def test_invite_key_is_single_use(ctx):
    client, _ = ctx
    await _login(client, **ADMIN)
    inv = await _invite_hunter(client, "h3@example.com")
    assert (await _register(client, email="h3@example.com", name="X", key=inv["key"])).status_code == 200
    # second redemption of the same key fails
    assert (await _register(client, email="h3@example.com", name="Y", key=inv["key"])).status_code == 401


@pytest.mark.asyncio
async def test_expired_invite_is_rejected(ctx):
    client, maker = ctx
    await _login(client, **ADMIN)
    inv = await _invite_hunter(client, "h4@example.com")
    async with maker() as s:
        row = (await s.execute(select(Invite).where(Invite.email == "h4@example.com"))).scalar_one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await s.commit()
    assert (await _register(client, email="h4@example.com", name="X", key=inv["key"])).status_code == 401


@pytest.mark.asyncio
async def test_duplicate_email_invite_conflicts(ctx):
    client, _ = ctx
    await _login(client, **ADMIN)
    await _invite_hunter(client, "dup@example.com")
    # admin email already an account
    assert (await client.post("/api/invites/hunter", json={"email": ADMIN["email"]})).status_code == 409
    # pending invite already exists
    assert (await client.post("/api/invites/hunter", json={"email": "dup@example.com"})).status_code == 409


@pytest.mark.asyncio
async def test_hunter_invites_va_creates_assignment(ctx):
    client, maker = ctx
    hunter_id = await _make_hunter(client)
    va_id = (await _make_va(client))[0]

    me = await client.get("/api/auth/me")
    assert me.json()["type"] == "va"
    async with maker() as s:
        va = await s.get(Va, va_id)
        assert va is not None and va.whatsapp_jid == "2348012345678@s.whatsapp.net"
        assign = (await s.execute(
            select(VaAssignment).where(VaAssignment.va_id == va_id)
        )).scalar_one()
        assert assign.user_id == hunter_id


@pytest.mark.asyncio
async def test_va_login_password_only(ctx):
    client, _ = ctx
    await _make_hunter(client)
    _, _key, password = await _make_va(client, "pinva@example.com")
    ok = await client.post(
        "/api/auth/login",
        json={"email": "pinva@example.com", "password": password},
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_va_signup_link_includes_kind(ctx):
    client, _ = ctx
    await _make_hunter(client)
    inv = await client.post(
        "/api/invites/va",
        json={"email": "linkva@example.com", "whatsapp": "+2348012345678"},
    )
    assert inv.status_code == 200, inv.text
    assert "kind=va" in inv.json()["signup_link"]


@pytest.mark.asyncio
async def test_va_blocked_from_sensitive_and_invites(ctx):
    client, _ = ctx
    await _make_hunter(client)
    await _make_va(client)  # cookie now = VA

    # cannot edit sensitive source content
    assert (await client.get("/api/profiles")).status_code == 403
    # cannot invite anyone
    assert (await client.post("/api/invites/va",
            json={"email": "x@e.com", "whatsapp": "+2340000000"})).status_code == 403
    assert (await client.post("/api/invites/hunter", json={"email": "y@e.com"})).status_code == 403


@pytest.mark.asyncio
async def test_va_sees_assigned_hunter_jobs_only(ctx):
    client, maker = ctx
    hunter_id = await _make_hunter(client)
    # a second, unrelated hunter with their own job
    async with maker() as s:
        other = User(email="other@example.com", password_hash=hash_password("x"),
                     name="Other", role=UserRole.hunter)
        s.add(other)
        await s.flush()
        s.add(Job(user_id=hunter_id, source=JobSourceName.greenhouse, origin=Origin.auto,
                  dedupe_key="dk-mine", company="Acme", title="Backend Engineer",
                  role_title="Backend Engineer", description="Go", track=Track.backend,
                  status=JobStatus.ready))
        s.add(Job(user_id=other.id, source=JobSourceName.greenhouse, origin=Origin.auto,
                  dedupe_key="dk-other", company="Globex", title="Backend Engineer",
                  role_title="Backend Engineer", description="Go", track=Track.backend,
                  status=JobStatus.ready))
        await s.commit()

    await _make_va(client)  # assigned to hunter_id (all tracks), cookie = VA
    jobs = await client.get("/api/jobs")
    assert jobs.status_code == 200
    companies = {j["company"] for j in jobs.json()}
    assert companies == {"Acme"}  # never sees Globex (other hunter)

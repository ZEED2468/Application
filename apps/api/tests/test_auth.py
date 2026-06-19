"""Auth end-to-end against the ASGI app with a SQLite-backed session override."""

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


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as s:
        s.add(
            User(
                email="hunter@example.com",
                password_hash=hash_password("s3cret"),
                name="Hunter One",
                role=UserRole.hunter,
            )
        )
        await s.commit()

    async def _override():
        async with maker() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    # https so the auth cookies (Secure whenever COOKIE_SAMESITE=none) are sent back.
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_me_logout(client):
    bad = await client.post(
        "/api/auth/login", json={"email": "hunter@example.com", "password": "wrong"}
    )
    assert bad.status_code == 401

    ok = await client.post(
        "/api/auth/login", json={"email": "hunter@example.com", "password": "s3cret"}
    )
    assert ok.status_code == 200
    assert ok.json()["type"] == "user"
    assert "access_token" in ok.cookies

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "hunter@example.com"

    out = await client.post("/api/auth/logout")
    assert out.status_code == 200


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401

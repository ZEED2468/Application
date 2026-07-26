"""Per-user LLM credentials (R1 BYO-key) + actionable errors (R7)."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import UserRole
from app.db import get_session
from app.llm import config, context, crypto
from app.main import app
from app.models import Base
from app.models.user import User
from app.security import hash_password

HUNTER = {"email": "hunter@example.com", "password": "s3cretpw"}


def test_crypto_roundtrip_and_mask():
    enc = crypto.encrypt("sk-secret-abcd")
    assert enc != "sk-secret-abcd"
    assert crypto.decrypt(enc) == "sk-secret-abcd"
    m = crypto.mask("sk-secret-abcd")
    assert m.endswith("abcd") and "secret" not in m
    assert crypto.decrypt("not-a-valid-token") is None


def test_resolve_prefers_user_override():
    token = context.set_user_llm({
        "provider": "openai", "model": "llama-x", "api_key": "sk-test",
        "base_url": "https://api.groq.com/openai/v1",
    })
    try:
        r = config.resolve("tailoring")
        assert r.provider == "openai" and r.api_key == "sk-test"
        assert r.base_url.endswith("groq.com/openai/v1") and r.model == "llama-x"
    finally:
        context.reset_user_llm(token)


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(User(email=HUNTER["email"], password_hash=hash_password(HUNTER["password"]),
                   name="Hunter", role=UserRole.hunter))
        await s.commit()

    async def _override():
        async with maker() as s:
            yield s
            await s.commit()

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c, maker
    app.dependency_overrides.clear()
    await engine.dispose()


async def _login(client, email=HUNTER["email"], password=HUNTER["password"]) -> UUID:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return UUID(r.json()["id"])


@pytest.mark.asyncio
async def test_llm_key_crud_validate_preferred(ctx):
    client, _ = ctx
    await _login(client)

    up = await client.post("/api/settings/llm-keys", json={
        "provider": "openai", "api_key": "sk-abc123",
        "base_url": "https://api.groq.com/openai/v1",
    })
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["has_key"] and body["masked_key"].endswith("c123") and body["status"] == "unknown"

    lst = await client.get("/api/settings/llm-keys")
    assert lst.status_code == 200 and len(lst.json()) == 1
    assert "sk-abc123" not in lst.text  # never returns plaintext

    v = await client.post("/api/settings/llm-keys/openai/validate")
    assert v.status_code == 200 and v.json()["status"] == "configured"  # fake mode

    p = await client.put("/api/settings/llm-keys/openai/preferred")
    assert p.json()["is_preferred"] is True

    d = await client.delete("/api/settings/llm-keys/openai")
    assert d.status_code == 200
    assert (await client.get("/api/settings/llm-keys")).json() == []


@pytest.mark.asyncio
async def test_llm_key_is_user_scoped(ctx):
    client, maker = ctx
    await _login(client)
    await client.post("/api/settings/llm-keys", json={"provider": "anthropic", "api_key": "sk-mine"})

    async with maker() as s:
        s.add(User(email="other@example.com", password_hash=hash_password("x"),
                   name="Other", role=UserRole.hunter))
        await s.commit()
    await client.post("/api/auth/login", json={"email": "other@example.com", "password": "x"})
    assert (await client.get("/api/settings/llm-keys")).json() == []


@pytest.mark.asyncio
async def test_unsupported_provider_returns_actionable_error(ctx):
    client, _ = ctx
    await _login(client)
    r = await client.post("/api/settings/llm-keys", json={"provider": "cohere", "api_key": "x"})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "domain_error" and "provider" in body["error"].lower()

"""AI Integrations: templates, CRUD, default, validate/health, discovery, and that
the routing override prefers the default integration."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import UserRole
from app.db import get_session
from app.llm import credentials, crypto
from app.main import app
from app.models import Base
from app.models.ai_integration import AiIntegration
from app.models.user import User
from app.security import hash_password

HUNTER = {"email": "hunter@example.com", "password": "s3cretpw"}


@pytest_asyncio.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add(User(email=HUNTER["email"], password_hash=hash_password(HUNTER["password"]),
                   name="Hunter One", role=UserRole.hunter))
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


async def _login(client) -> UUID:
    r = await client.post("/api/auth/login", json=HUNTER)
    assert r.status_code == 200, r.text
    return UUID(r.json()["id"])


@pytest.mark.asyncio
async def test_templates(ctx):
    client, _ = ctx
    await _login(client)
    r = await client.get("/api/integrations/templates")
    assert r.status_code == 200, r.text
    ids = {t["id"] for t in r.json()}
    assert {"anthropic", "google", "openai", "custom"} <= ids
    openai = next(t for t in r.json() if t["id"] == "openai")
    assert any(f["id"] == "base_url" for f in openai["fields"])


@pytest.mark.asyncio
async def test_crud_default_validate_health(ctx):
    client, _ = ctx
    await _login(client)

    created = await client.post("/api/integrations", json={
        "template": "openai", "name": "Groq", "base_url": "https://api.groq.com/openai/v1",
        "api_key": "sk-test-123", "model": "llama-3.1-70b",
    })
    assert created.status_code == 200, created.text
    it = created.json()
    assert it["provider"] == "openai" and it["is_default"] is True  # first -> default
    assert it["has_key"] is True and it["masked_key"].endswith("-123")
    iid = it["id"]

    # a second integration is not default
    second = (await client.post("/api/integrations", json={"template": "anthropic", "api_key": "sk-ant-x"})).json()
    assert second["is_default"] is False
    lst = (await client.get("/api/integrations")).json()
    assert len(lst) == 2

    # switch default
    made = await client.put(f"/api/integrations/{second['id']}/default")
    assert made.status_code == 200 and made.json()["is_default"] is True

    # validate (fake mode -> configured) + health reflects it
    val = await client.post(f"/api/integrations/{iid}/validate")
    assert val.status_code == 200 and val.json()["status"] == "configured"
    hp = await client.get(f"/api/integrations/{iid}/health")
    assert hp.json()["status"] == "configured"

    # delete
    assert (await client.delete(f"/api/integrations/{iid}")).status_code == 200
    assert len(((await client.get("/api/integrations")).json())) == 1


@pytest.mark.asyncio
async def test_discover_models(ctx):
    client, _ = ctx
    await _login(client)
    it = (await client.post("/api/integrations", json={"template": "openai", "api_key": "k"})).json()
    disc = await client.get(f"/api/integrations/{it['id']}/models/discover")
    assert disc.status_code == 200
    assert "gpt-4o-mini" in disc.json()["models"]  # fake-mode static list
    # manual add
    added = await client.post(f"/api/integrations/{it['id']}/models", json={"model": "my-model"})
    assert "my-model" in added.json()["models"]


@pytest.mark.asyncio
async def test_routing_prefers_default_integration(ctx):
    client, maker = ctx
    uid = await _login(client)
    async with maker() as s:
        s.add(AiIntegration(user_id=uid, name="Groq", provider="openai",
                            base_url="https://api.groq.com/openai/v1",
                            encrypted_api_key=crypto.encrypt("sk-secret"), model="llama-3.1-70b",
                            is_default=True))
        await s.commit()
    async with maker() as s:
        override = await credentials.load_preferred_override(s, uid)
    assert override == {"provider": "openai", "model": "llama-3.1-70b",
                        "api_key": "sk-secret", "base_url": "https://api.groq.com/openai/v1"}

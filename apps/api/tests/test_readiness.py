"""GET /api/user/readiness — centralized onboarding/setup progress."""

from __future__ import annotations

from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import ParseStatus, Track, UserRole
from app.db import get_session
from app.main import app
from app.models import Base
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.models.user_llm_credential import UserLlmCredential
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
async def test_readiness_empty(ctx):
    client, _ = ctx
    await _login(client)
    r = await client.get("/api/user/readiness")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["progress"] == 0 and body["complete"] is False
    assert body["next_action"]["id"] == "ai_provider"
    assert {s["id"] for s in body["steps"]} == {
        "ai_provider", "track_created", "resume_uploaded",
        "profile_confirmed", "cover_letter_template",
    }
    assert all(s["completed"] is False for s in body["steps"])


@pytest.mark.asyncio
async def test_readiness_partial(ctx):
    client, maker = ctx
    uid = await _login(client)
    async with maker() as s:
        s.add(UserLlmCredential(user_id=uid, provider="anthropic",
                                encrypted_api_key="enc", status="configured", is_active=True))
        s.add(RoleCv(user_id=uid, track=Track.backend, original_filename="cv.pdf",
                     source_file_key=f"{uid}/role-cv/backend/source.pdf",
                     parse_status=ParseStatus.parsed))
        s.add(MasterProfile(user_id=uid, track=Track.backend, skills=["Go"], experience=[],
                            education=[], projects=[], links={}, confirmed=True))
        await s.commit()

    r = await client.get("/api/user/readiness")
    body = r.json()
    done = {s["id"] for s in body["steps"] if s["completed"]}
    assert done == {"ai_provider", "track_created", "resume_uploaded", "profile_confirmed"}
    assert body["progress"] == 80  # 4 of 5
    assert body["next_action"]["id"] == "cover_letter_template"
    assert body["api_key_validated"] is True
    backend = next(t for t in body["tracks"] if t["slug"] == "backend")
    assert backend["status"] == "ready" and backend["resume"] is True

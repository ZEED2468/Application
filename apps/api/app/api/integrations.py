"""AI Integrations API — the central hub for configuring AI providers.

A user may have many integrations (built from a template or fully custom). Keys are
encrypted at rest and never returned in plaintext. `is_default` selects the one the
routing engine uses. The frontend renders config forms purely from template schemas.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import current_user
from app.llm import crypto
from app.llm.credentials import validate_key
from app.llm.discovery import discover_models
from app.llm.providers import get as get_provider
from app.llm.templates import get_template, get_templates
from app.models.ai_integration import AiIntegration
from app.models.user import User

router = APIRouter(prefix="/integrations", tags=["integrations"])
log = structlog.get_logger(__name__)

_ADAPTERS = {"anthropic", "openai", "google"}


class IntegrationIn(BaseModel):
    template: str | None = None
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    config: dict = {}


class ModelIn(BaseModel):
    model: str


class IntegrationOut(BaseModel):
    id: str
    name: str
    provider: str
    template: str | None = None
    base_url: str | None = None
    model: str | None = None
    masked_key: str | None = None
    has_key: bool = False
    models: list[str] = []
    capabilities: dict = {}
    status: str = "unknown"
    is_default: bool = False
    last_validated_at: str | None = None


def _out(row: AiIntegration) -> IntegrationOut:
    plain = crypto.decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
    return IntegrationOut(
        id=str(row.id), name=row.name, provider=row.provider, template=row.template,
        base_url=row.base_url, model=row.model,
        masked_key=crypto.mask(plain) if plain else None,
        has_key=bool(row.encrypted_api_key),
        models=list(row.models or []), capabilities=row.capabilities or {},
        status=row.status, is_default=row.is_default,
        last_validated_at=row.last_validated_at.isoformat() if row.last_validated_at else None,
    )


async def _get(session: AsyncSession, user_id, integration_id: UUID) -> AiIntegration:
    row = await session.get(AiIntegration, integration_id)
    if row is None or row.user_id != user_id:
        raise NotFoundError("Integration not found")
    return row


async def _all(session, user_id) -> list[AiIntegration]:
    return list((await session.execute(
        select(AiIntegration).where(AiIntegration.user_id == user_id)
    )).scalars().all())


@router.get("/templates")
async def list_templates(user: User = Depends(current_user)) -> list[dict]:
    """Built-in provider templates + their config-field schemas (drives dynamic forms)."""
    return get_templates()


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> list[IntegrationOut]:
    return [_out(r) for r in await _all(session, user.id)]


@router.post("", response_model=IntegrationOut)
async def create_integration(
    body: IntegrationIn,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    tpl = get_template(body.template) if body.template else None
    provider = (body.provider or (tpl["provider"] if tpl else "")).strip().lower()
    if provider not in _ADAPTERS:
        raise DomainError(
            f"Unknown provider '{provider}'. Use a template or one of: {', '.join(sorted(_ADAPTERS))}.",
            title="Invalid provider",
        )
    get_provider(provider)  # sanity: adapter exists
    name = (body.name or (tpl["name"] if tpl else provider.title())).strip()
    if not name:
        raise DomainError("An integration name is required.", title="Name required")

    existing = await _all(session, user.id)
    row = AiIntegration(
        user_id=user.id, name=name, provider=provider, template=body.template,
        base_url=(body.base_url or "").strip() or None,
        model=(body.model or "").strip() or None,
        config=body.config or {}, models=[], capabilities={},
        is_default=(len(existing) == 0),  # first integration becomes the default
    )
    if body.api_key and body.api_key.strip():
        row.encrypted_api_key = crypto.encrypt(body.api_key.strip())
    session.add(row)
    await session.flush()
    return _out(row)


@router.put("/{integration_id}", response_model=IntegrationOut)
async def update_integration(
    integration_id: UUID, body: IntegrationIn,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    row = await _get(session, user.id, integration_id)
    if body.name is not None:
        row.name = body.name.strip() or row.name
    if body.base_url is not None:
        row.base_url = body.base_url.strip() or None
    if body.model is not None:
        row.model = body.model.strip() or None
    if body.config:
        row.config = body.config
    if body.api_key and body.api_key.strip():
        row.encrypted_api_key = crypto.encrypt(body.api_key.strip())
        row.status = "unknown"  # re-validate after a key change
    await session.flush()
    return _out(row)


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    row = await _get(session, user.id, integration_id)
    was_default = row.is_default
    await session.delete(row)
    await session.flush()
    # Promote another integration to default if we removed the default one.
    if was_default:
        rest = await _all(session, user.id)
        if rest:
            rest[0].is_default = True
    await session.flush()
    return {"deleted": str(integration_id)}


@router.put("/{integration_id}/default", response_model=IntegrationOut)
async def set_default(
    integration_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    row = await _get(session, user.id, integration_id)
    await session.execute(
        update(AiIntegration).where(AiIntegration.user_id == user.id).values(is_default=False)
    )
    row.is_default = True
    await session.flush()
    return _out(row)


@router.post("/{integration_id}/validate", response_model=IntegrationOut)
async def validate_integration(
    integration_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    row = await _get(session, user.id, integration_id)
    key = crypto.decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
    t0 = time.monotonic()
    status = await validate_key(
        provider=row.provider, api_key=key or "", base_url=row.base_url, model=row.model
    )
    row.status = status
    row.last_validated_at = datetime.now(timezone.utc)
    row.capabilities = {**(row.capabilities or {}), "latency_ms": round((time.monotonic() - t0) * 1000)}
    await session.flush()
    return _out(row)


@router.get("/{integration_id}/health")
async def health(
    integration_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """Cheap, pollable health snapshot (stored status; use /validate to re-check live)."""
    row = await _get(session, user.id, integration_id)
    return {
        "id": str(row.id), "status": row.status,
        "last_validated_at": row.last_validated_at.isoformat() if row.last_validated_at else None,
        "latency_ms": (row.capabilities or {}).get("latency_ms"),
    }


@router.get("/{integration_id}/models/discover", response_model=IntegrationOut)
async def discover(
    integration_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    row = await _get(session, user.id, integration_id)
    key = crypto.decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
    found = await discover_models(provider=row.provider, api_key=key, base_url=row.base_url)
    if found:
        row.models = found
        await session.flush()
    return _out(row)


@router.post("/{integration_id}/models", response_model=IntegrationOut)
async def add_model(
    integration_id: UUID, body: ModelIn,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> IntegrationOut:
    row = await _get(session, user.id, integration_id)
    m = (body.model or "").strip()
    if not m:
        raise DomainError("A model id is required.")
    models = list(row.models or [])
    if m not in models:
        models.append(m)
        row.models = models
        await session.flush()
    return _out(row)

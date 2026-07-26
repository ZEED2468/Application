"""User settings API — manage per-user LLM provider keys (R1 BYO-key).

Keys are stored encrypted and never returned in plaintext; the client sees a masked
form + a status (configured | invalid | unreachable | unknown).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import current_user
from app.llm import crypto
from app.llm.credentials import validate_key
from app.llm.providers import get as get_provider
from app.models.user import User
from app.models.user_llm_credential import UserLlmCredential

router = APIRouter(prefix="/settings", tags=["settings"])

_ALLOWED_PROVIDERS = {"anthropic", "openai", "google"}


class LlmKeyIn(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    label: str | None = None


class LlmKeyOut(BaseModel):
    provider: str
    label: str | None = None
    masked_key: str | None = None
    has_key: bool = False
    base_url: str | None = None
    model: str | None = None
    is_active: bool = True
    is_preferred: bool = False
    status: str = "unknown"
    last_validated_at: str | None = None


def _out(row: UserLlmCredential) -> LlmKeyOut:
    plain = crypto.decrypt(row.encrypted_api_key) if row.encrypted_api_key else None
    return LlmKeyOut(
        provider=row.provider, label=row.label,
        masked_key=crypto.mask(plain) if plain else None,
        has_key=bool(row.encrypted_api_key),
        base_url=row.base_url, model=row.model,
        is_active=row.is_active, is_preferred=row.is_preferred,
        status=row.status,
        last_validated_at=row.last_validated_at.isoformat() if row.last_validated_at else None,
    )


async def _get(session, user_id, provider) -> UserLlmCredential | None:
    return (await session.execute(
        select(UserLlmCredential).where(
            UserLlmCredential.user_id == user_id,
            UserLlmCredential.provider == provider,
        )
    )).scalar_one_or_none()


def _check_provider(provider: str) -> str:
    p = (provider or "").strip().lower()
    if p not in _ALLOWED_PROVIDERS:
        raise DomainError(
            f"Unsupported provider '{provider}'. Use one of: {', '.join(sorted(_ALLOWED_PROVIDERS))} "
            "(OpenAI-compatible hosts like Groq/Together/OpenRouter/Ollama use 'openai' + a base URL).",
        )
    return p


@router.get("/llm-keys", response_model=list[LlmKeyOut])
async def list_llm_keys(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> list[LlmKeyOut]:
    rows = (await session.execute(
        select(UserLlmCredential).where(UserLlmCredential.user_id == user.id)
    )).scalars().all()
    return [_out(r) for r in rows]


@router.post("/llm-keys", response_model=LlmKeyOut)
async def upsert_llm_key(
    body: LlmKeyIn,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> LlmKeyOut:
    provider = _check_provider(body.provider)
    get_provider(provider)  # sanity: adapter exists
    row = await _get(session, user.id, provider)
    if row is None:
        row = UserLlmCredential(user_id=user.id, provider=provider)
        session.add(row)
    row.label = body.label
    row.base_url = (body.base_url or "").strip() or None
    row.model = (body.model or "").strip() or None
    if body.api_key and body.api_key.strip():
        row.encrypted_api_key = crypto.encrypt(body.api_key.strip())
        row.status = "unknown"  # re-validate after a key change
    await session.flush()
    return _out(row)


@router.delete("/llm-keys/{provider}")
async def delete_llm_key(
    provider: str,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    row = await _get(session, user.id, _check_provider(provider))
    if row is None:
        raise NotFoundError("No key stored for this provider.")
    await session.delete(row)
    await session.flush()
    return {"deleted": provider}


@router.post("/llm-keys/{provider}/validate", response_model=LlmKeyOut)
async def validate_llm_key(
    provider: str,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> LlmKeyOut:
    row = await _get(session, user.id, _check_provider(provider))
    if row is None or not row.encrypted_api_key:
        raise NotFoundError("Add a key for this provider first.")
    key = crypto.decrypt(row.encrypted_api_key)
    if not key:
        row.status = "invalid"
    else:
        row.status = await validate_key(
            provider=row.provider, api_key=key, base_url=row.base_url, model=row.model
        )
    row.last_validated_at = datetime.now(timezone.utc)
    await session.flush()
    return _out(row)


@router.put("/llm-keys/{provider}/preferred", response_model=LlmKeyOut)
async def set_preferred(
    provider: str,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> LlmKeyOut:
    p = _check_provider(provider)
    row = await _get(session, user.id, p)
    if row is None:
        raise NotFoundError("No key stored for this provider.")
    await session.execute(
        update(UserLlmCredential)
        .where(UserLlmCredential.user_id == user.id)
        .values(is_preferred=False)
    )
    row.is_preferred = True
    await session.flush()
    return _out(row)

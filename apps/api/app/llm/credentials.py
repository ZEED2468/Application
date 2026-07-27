"""Per-user LLM credential storage helpers + validation (R1 BYO-key).

Loads a user's preferred/active provider key, decrypts it, and (for the request)
exposes it as an override consumed by `config.resolve()` via `llm.context`.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.config import settings
from app.llm import crypto
from app.llm.providers import get as get_provider
from app.models.ai_integration import AiIntegration
from app.models.user_llm_credential import UserLlmCredential


async def load_preferred_override(session, user_id) -> dict | None:
    """The user's default (else any) usable provider config as a resolve override.

    Prefers the new AI Integrations; falls back to the legacy `user_llm_credential`
    during the transition so nobody's key stops working before backfill/migration.
    """
    integrations = (await session.execute(
        select(AiIntegration).where(AiIntegration.user_id == user_id)
    )).scalars().all()
    if integrations:
        integrations = sorted(integrations, key=lambda r: (not r.is_default))  # default first
        for r in integrations:
            if not r.encrypted_api_key:
                continue
            key = crypto.decrypt(r.encrypted_api_key)
            if key:
                return {"provider": r.provider, "model": r.model, "api_key": key,
                        "base_url": r.base_url or ""}

    rows = (await session.execute(
        select(UserLlmCredential).where(
            UserLlmCredential.user_id == user_id,
            UserLlmCredential.is_active.is_(True),
        )
    )).scalars().all()
    rows = sorted(rows, key=lambda r: (not r.is_preferred))  # preferred first
    for r in rows:
        if not r.encrypted_api_key:
            continue
        key = crypto.decrypt(r.encrypted_api_key)
        if key:
            return {"provider": r.provider, "model": r.model, "api_key": key,
                    "base_url": r.base_url or ""}
    return None


async def validate_key(*, provider: str, api_key: str, base_url: str | None, model: str | None) -> str:
    """Return a status: configured | invalid | unreachable. Skips the network in
    fake mode (can't reach a provider) and reports based on key presence."""
    if settings.use_fake_integrations:
        return "configured" if api_key else "invalid"
    try:
        prov = get_provider(provider)
    except ValueError:
        return "invalid"
    try:
        # A real round-trip: max_tokens=1 makes some providers (Gemini) return a
        # truncated response with no text, which used to read as "unreachable".
        await asyncio.wait_for(
            prov.complete(system="You are a health check.", prompt="Reply with: ok",
                          model=model or prov.default_model,
                          api_key=api_key, base_url=base_url or "", max_tokens=16),
            timeout=20,
        )
        return "configured"
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if any(t in msg for t in ("401", "403", "auth", "invalid", "api key", "unauthor")):
            return "invalid"
        return "unreachable"

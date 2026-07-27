"""Automatic model discovery per provider (best-effort).

Where the provider exposes a list-models endpoint we fetch it; otherwise we return a
known static list (Anthropic) or an empty list (caller then allows manual entry).
"""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

_STATIC = {
    "anthropic": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-4o", "gpt-4o-mini"],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro"],
}


async def discover_models(*, provider: str, api_key: str | None, base_url: str | None) -> list[str]:
    if settings.use_fake_integrations:
        return _STATIC.get(provider, [])
    try:
        if provider == "anthropic":
            return _STATIC["anthropic"]  # no public list endpoint
        if provider == "google":
            base = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
            async with httpx.AsyncClient(timeout=15) as c:
                resp = await c.get(f"{base}/models", params={"key": api_key or ""})
                resp.raise_for_status()
                data = resp.json()
            return [m["name"].split("/")[-1] for m in data.get("models", []) if "name" in m]
        # openai-compatible
        base = (base_url or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(f"{base}/models", headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return [m["id"] for m in data.get("data", []) if "id" in m]
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort; fall back to manual
        log.warning("model_discovery_failed", provider=provider, error=str(exc))
        return []

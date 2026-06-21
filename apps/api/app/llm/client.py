"""Provider-agnostic LLM facade.

The six AI features call only `is_live()` + `complete_text()`. This module
resolves the configured provider/model (globally or per-feature) and dispatches
to it. In fake mode (`USE_FAKE_INTEGRATIONS=true`) `is_live()` is False and the
features take their deterministic path — no provider is ever called.
"""

from __future__ import annotations

import structlog

from app.config import settings
from app.llm import config as llm_config
from app.llm.providers import get as get_provider

log = structlog.get_logger(__name__)


def is_live(feature: str | None = None) -> bool:
    """True when a real model should be used for this feature."""
    if settings.use_fake_integrations:
        return False
    return llm_config.resolve(feature).is_usable()


async def complete_text(
    system: str, prompt: str, *, max_tokens: int = 1500, feature: str | None = None
) -> str:
    """Single-turn completion via the configured provider for `feature`."""
    resolved = llm_config.resolve(feature)
    if not resolved.is_usable():
        raise RuntimeError(
            f"LLM not configured for feature={feature!r} (provider={resolved.provider})"
        )
    provider = get_provider(resolved.provider)
    log.info("llm.complete", feature=feature, provider=resolved.provider, model=resolved.model)
    return await provider.complete(
        system=system, prompt=prompt, model=resolved.model,
        api_key=resolved.api_key, base_url=resolved.base_url, max_tokens=max_tokens,
    )


async def try_complete_text(
    system: str, prompt: str, *, max_tokens: int = 1500, feature: str | None = None
) -> str | None:
    """Like `complete_text`, but returns None when the provider call fails."""
    try:
        return await complete_text(
            system, prompt, max_tokens=max_tokens, feature=feature,
        )
    except Exception as exc:
        log.warning(
            "llm.complete_failed",
            feature=feature,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        return None

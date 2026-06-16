"""Thin Anthropic wrapper. In fake mode (no key / use_fake_integrations) the
high-level llm functions take a deterministic path and never call this."""

from __future__ import annotations

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


def is_live() -> bool:
    return bool(settings.anthropic_api_key) and not settings.use_fake_integrations


async def complete_text(system: str, prompt: str, *, max_tokens: int = 1500) -> str:
    """Single-turn completion. Raises if called without a configured key."""
    if not is_live():
        raise RuntimeError("LLM not configured; callers must use the fake path")
    # Imported lazily so the dependency isn't required in fake/dev/test runs.
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in msg.content if block.type == "text")

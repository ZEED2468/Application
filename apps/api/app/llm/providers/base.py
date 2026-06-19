"""LLM provider abstraction.

A provider knows how to turn (system, prompt, model) into text for one API shape.
Providers are registered by name; the client facade picks one per the resolved
config. Adding a provider is a new file + `register`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    # Whether an API key is mandatory (False for keyless local servers).
    requires_key: bool
    # Used when no model is configured anywhere.
    default_model: str

    async def complete(
        self, *, system: str, prompt: str, model: str, api_key: str, base_url: str,
        max_tokens: int,
    ) -> str: ...


REGISTRY: dict[str, LLMProvider] = {}


def register(provider: LLMProvider) -> LLMProvider:
    instance = provider() if isinstance(provider, type) else provider
    REGISTRY[instance.name] = instance
    return provider


def get(name: str) -> LLMProvider:
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown LLM provider '{name}'. Available: {sorted(REGISTRY)}"
        )
    return REGISTRY[name]

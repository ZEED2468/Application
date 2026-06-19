"""LLM providers. Importing this package registers every adapter."""

from app.llm.providers import anthropic, google, openai_compat  # noqa: F401
from app.llm.providers.base import REGISTRY, LLMProvider, get, register

__all__ = ["REGISTRY", "LLMProvider", "get", "register"]

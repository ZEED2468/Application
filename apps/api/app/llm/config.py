"""Resolve which provider/model/key/base_url powers a given AI feature.

Resolution order (per field): per-feature env override -> global `LLM_*` ->
legacy `ANTHROPIC_*` (back-compat for the original Anthropic-only setup).

Per-feature overrides are read from the environment as
`LLM_<FEATURE>_{PROVIDER,MODEL,API_KEY,BASE_URL}` so we don't have to declare ~20
pydantic fields. Example: `LLM_TAILORING_MODEL=claude-opus-4-8`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.config import settings
from app.llm.providers import get as get_provider

# Features that may be LLM-backed (each can override the global default).
FEATURES = {
    "tailoring", "cover_letter", "hookfinder", "draft_email", "classify_reply",
    "ats_vet", "ats_analyze", "cv_structure", "track_classify",
}


@dataclass(slots=True)
class ResolvedLLM:
    provider: str
    model: str
    api_key: str
    base_url: str

    def is_usable(self) -> bool:
        """True if this config can actually call a model (key present, or the
        provider needs no key — e.g. a local OpenAI-compatible server)."""
        prov = get_provider(self.provider)
        return bool(self.api_key) or not prov.requires_key


def _feature_env(feature: str | None, field: str) -> str | None:
    if not feature:
        return None
    return os.getenv(f"LLM_{feature.upper()}_{field.upper()}") or None


def resolve(feature: str | None = None) -> ResolvedLLM:
    provider = (
        _feature_env(feature, "provider")
        or settings.llm_provider
        or "anthropic"
    )
    model = _feature_env(feature, "model") or settings.llm_model or ""
    api_key = _feature_env(feature, "api_key") or settings.llm_api_key or ""
    base_url = _feature_env(feature, "base_url") or settings.llm_base_url or ""

    # Legacy fallback so an existing ANTHROPIC_* setup keeps working unchanged.
    if provider == "anthropic":
        api_key = api_key or settings.anthropic_api_key
        model = model or settings.anthropic_model

    # If still no model, let the provider's default apply at call time.
    if not model:
        model = get_provider(provider).default_model

    return ResolvedLLM(provider=provider, model=model, api_key=api_key, base_url=base_url)

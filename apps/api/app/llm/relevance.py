"""Relevance prefilter — rule-based token overlap between the job and the
hunter's profile skills. Cheap, deterministic, no LLM (PRD: rules first)."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9+#.]+")

# Below this, the job is discarded/held (Open Decision §11.24 — tune later).
RELEVANCE_THRESHOLD = 0.12


def _tokens(text: str | None) -> set[str]:
    return set(_TOKEN.findall((text or "").lower()))


def score(*, title: str, description: str | None, skills: list[str]) -> float:
    """Fraction of the profile's skill tokens that appear in the job text."""
    skill_tokens = {t for s in skills for t in _tokens(s)}
    if not skill_tokens:
        return 0.0
    job_tokens = _tokens(title) | _tokens(description)
    hits = skill_tokens & job_tokens
    return round(len(hits) / len(skill_tokens), 4)


def passes(score_value: float) -> bool:
    return score_value >= RELEVANCE_THRESHOLD

"""The assembled default registry — the single source of truth for the rule set.

One list, consumed at four points. `default_registry()` returns a fresh Registry
so its `version()` can be pinned per run.
"""

from __future__ import annotations

from app.cv_engine.rules import grounding, rendered, structure
from app.cv_engine.rules.base import Registry

_ALL = [*structure.RULES, *grounding.RULES, *rendered.RULES]


def default_registry() -> Registry:
    return Registry(rules=list(_ALL))

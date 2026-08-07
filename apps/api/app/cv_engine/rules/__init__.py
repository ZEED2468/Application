"""The rule registry — one definition, four consumption points.

A rule is defined once and consumed at INGEST (vocabulary), DIAGNOSE (checks),
PATCH (remedies), and RENDER (parameters). This package holds the base types
(`base`), the deterministic rule sets (`structure`, `rendered`, `grounding`),
and the assembled default registry (`registry.default_registry`).
"""

from app.cv_engine.rules.registry import default_registry

__all__ = ["default_registry"]

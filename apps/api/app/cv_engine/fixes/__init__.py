"""Deterministic fixes — the zero-LLM PATCH phase ("we fixed your CV's format").

Pure, grounding-safe transforms over a cv_json: they reformat/trim existing text
(dates, whitespace, links) but never invent a number or entity, so the artifact still
grounds against the original-input ledger. Each transform reports what it changed as a
list of FixRecord dicts for the delta report.
"""

from app.cv_engine.fixes.deterministic import (
    FIX_MAP,
    normalize_date_string,
    normalize_dates,
    tidy_links,
    tidy_text,
    tidy_value,
)

__all__ = [
    "FIX_MAP",
    "normalize_date_string",
    "normalize_dates",
    "tidy_links",
    "tidy_text",
    "tidy_value",
]

"""RawJob -> normalized fields, including the per-hunter dedupe key."""

from __future__ import annotations

import hashlib
import re

from app.sources.base import RawJob

_WS = re.compile(r"\s+")


def _norm(text: str | None) -> str:
    return _WS.sub(" ", (text or "").strip().lower())


def dedupe_key(raw: RawJob) -> str:
    """Stable hash of (company, title, location). Same posting -> same key, so
    `(user_id, dedupe_key)` UNIQUE collapses duplicates per hunter."""
    basis = "|".join((_norm(raw.company), _norm(raw.title), _norm(raw.location)))
    return hashlib.sha256(basis.encode()).hexdigest()[:32]


def to_job_fields(raw: RawJob) -> dict:
    return {
        "source": raw.source,
        "source_job_id": raw.source_job_id,
        "dedupe_key": dedupe_key(raw),
        "company": raw.company,
        "title": raw.title,
        "location": raw.location,
        "url": raw.url,
        "description": raw.description,
        "raw": raw.raw,
    }

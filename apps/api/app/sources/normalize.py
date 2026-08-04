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


def _cap(value: str | None, n: int) -> str | None:
    """Clamp to a VARCHAR(n) column. Providers can return very long values — SerpApi's
    `source_job_id` is a long base64 token — which must not blow up the insert."""
    return value[:n] if isinstance(value, str) and len(value) > n else value


def to_job_fields(raw: RawJob) -> dict:
    return {
        "source": raw.source,
        "source_job_id": _cap(raw.source_job_id, 255),
        "dedupe_key": dedupe_key(raw),
        "company": _cap(raw.company, 255),
        "title": _cap(raw.title, 255),
        "location": _cap(raw.location, 255),
        "url": raw.url,
        "description": raw.description,
        "raw": raw.raw,
    }

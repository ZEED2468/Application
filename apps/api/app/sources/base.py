"""Pluggable job-source interface.

Every source — whether a per-company board scraper (Greenhouse/Lever/Ashby) or
a keyword aggregator (Adzuna/SerpApi) — implements the same `JobSource` protocol
and registers via `@register`. Adding a source is a new file + decorator; nothing
downstream changes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.core.enums import JobSourceName, Track


@dataclass(slots=True)
class RawJob:
    """A posting as returned by a source, before normalization."""

    source: JobSourceName
    source_job_id: str | None
    company: str
    title: str
    location: str | None = None
    url: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    raw: dict = field(default_factory=dict)


@dataclass(slots=True)
class SourceQuery:
    """What to ask a source for, derived from a hunter's track + profile."""

    track: Track
    keywords: list[str] = field(default_factory=list)
    location: str | None = None
    # Board scrapers need company slugs/board tokens; aggregators ignore these.
    boards: list[str] = field(default_factory=list)
    limit: int = 50


@runtime_checkable
class JobSource(Protocol):
    name: JobSourceName

    def supports(self, track: Track) -> bool: ...

    def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]: ...


SOURCES: dict[JobSourceName, JobSource] = {}


def register(source: JobSource) -> JobSource:
    """Class decorator: instantiate and register a source by its name."""
    instance = source() if isinstance(source, type) else source
    SOURCES[instance.name] = instance
    return source


def active_sources() -> list[JobSource]:
    """Sources to actually poll. In fake/dev mode use the deterministic fake;
    otherwise the registered real adapters."""
    from app.config import settings
    from app.sources.fake import FakeSource

    if settings.use_fake_integrations:
        return [FakeSource()]
    return list(SOURCES.values())

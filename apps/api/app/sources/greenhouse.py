"""Greenhouse public board adapter. One board token per company."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import httpx

from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str | None) -> str | None:
    return _TAG_RE.sub(" ", text).strip() if text else None


@register
class GreenhouseSource:
    name = JobSourceName.greenhouse

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        async with httpx.AsyncClient(timeout=20) as client:
            for board in query.boards:
                url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError:
                    continue
                for job in resp.json().get("jobs", [])[: query.limit]:
                    yield RawJob(
                        source=self.name,
                        source_job_id=str(job.get("id")),
                        company=board,
                        title=job.get("title", ""),
                        location=(job.get("location") or {}).get("name"),
                        url=job.get("absolute_url"),
                        description=_strip_html(job.get("content")),
                        raw=job,
                    )

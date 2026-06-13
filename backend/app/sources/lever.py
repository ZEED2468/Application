"""Lever public postings adapter. One company slug per board."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register


@register
class LeverSource:
    name = JobSourceName.lever

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        async with httpx.AsyncClient(timeout=20) as client:
            for company in query.boards:
                url = f"https://api.lever.co/v0/postings/{company}?mode=json"
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError:
                    continue
                for job in resp.json()[: query.limit]:
                    cats = job.get("categories") or {}
                    yield RawJob(
                        source=self.name,
                        source_job_id=job.get("id"),
                        company=company,
                        title=job.get("text", ""),
                        location=cats.get("location"),
                        url=job.get("hostedUrl"),
                        description=job.get("descriptionPlain"),
                        raw=job,
                    )

"""Ashby public job-board adapter. One board name per company."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register


@register
class AshbySource:
    name = JobSourceName.ashby

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        async with httpx.AsyncClient(timeout=20) as client:
            for board in query.boards:
                url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
                try:
                    resp = await client.get(url, params={"includeCompensation": "true"})
                    resp.raise_for_status()
                except httpx.HTTPError:
                    continue
                for job in resp.json().get("jobs", [])[: query.limit]:
                    yield RawJob(
                        source=self.name,
                        source_job_id=job.get("id"),
                        company=board,
                        title=job.get("title", ""),
                        location=job.get("location"),
                        url=job.get("jobUrl"),
                        description=job.get("descriptionPlain") or job.get("description"),
                        raw=job,
                    )

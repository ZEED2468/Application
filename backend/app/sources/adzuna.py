"""Adzuna aggregator adapter (keyword + location search)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register


@register
class AdzunaSource:
    name = JobSourceName.adzuna

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        if not (settings.adzuna_app_id and settings.adzuna_app_key):
            return  # no creds -> no-op (tests/dev use the fake source)
        country = "gb"
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "what": " ".join(query.keywords) or query.track.value,
            "results_per_page": min(query.limit, 50),
        }
        if query.location:
            params["where"] = query.location
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPError:
                return
            for job in resp.json().get("results", []):
                yield RawJob(
                    source=self.name,
                    source_job_id=str(job.get("id")),
                    company=(job.get("company") or {}).get("display_name", "Unknown"),
                    title=job.get("title", ""),
                    location=(job.get("location") or {}).get("display_name"),
                    url=job.get("redirect_url"),
                    description=job.get("description"),
                    raw=job,
                )

"""SerpApi Google Jobs aggregator adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register


@register
class SerpApiSource:
    name = JobSourceName.serpapi

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        if not settings.serpapi_api_key:
            return  # no creds -> no-op
        params = {
            "engine": "google_jobs",
            "q": " ".join(query.keywords) or query.track.value,
            "api_key": settings.serpapi_api_key,
        }
        if query.location:
            params["location"] = query.location
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get("https://serpapi.com/search", params=params)
                resp.raise_for_status()
            except httpx.HTTPError:
                return
            for job in resp.json().get("jobs_results", [])[: query.limit]:
                yield RawJob(
                    source=self.name,
                    source_job_id=job.get("job_id"),
                    company=job.get("company_name", "Unknown"),
                    title=job.get("title", ""),
                    location=job.get("location"),
                    url=(job.get("related_links") or [{}])[0].get("link"),
                    description=job.get("description"),
                    raw=job,
                )

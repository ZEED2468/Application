"""SerpApi Google Jobs aggregator adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import structlog

from app.config import settings
from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register

log = structlog.get_logger(__name__)


@register
class SerpApiSource:
    name = JobSourceName.serpapi

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        if not settings.serpapi_api_key:
            return  # no creds -> no-op
        # Google Jobs narrows hard with many terms — use the top few skills only.
        q = " ".join(query.keywords[:3]) or query.track.value
        if not query.location:
            q = f"{q} remote"  # remote/global default when no location is set
        params = {
            "engine": "google_jobs",
            "q": q,
            "api_key": settings.serpapi_api_key,
        }
        if query.location:
            params["location"] = query.location
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get("https://serpapi.com/search", params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                log.warning("serpapi.http_error", status=exc.response.status_code,
                            body=exc.response.text[:300])
                raise RuntimeError(
                    f"serpapi {exc.response.status_code}: {exc.response.text[:120]}"
                ) from exc
            except httpx.HTTPError as exc:
                log.warning("serpapi.request_failed", error=str(exc))
                raise RuntimeError(f"serpapi request failed: {exc}") from exc
            data = resp.json()
            err = data.get("error")
            if err:  # SerpApi reports bad key / no credits / no-results in a 200 body
                low = str(err).lower()
                if "returned any results" in low or "no results" in low:
                    log.info("serpapi.no_results", q=q)  # benign: just an empty search
                    return
                log.warning("serpapi.api_error", error=str(err)[:300])
                raise RuntimeError(f"serpapi: {str(err)[:120]}")
            for job in data.get("jobs_results", [])[: query.limit]:
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

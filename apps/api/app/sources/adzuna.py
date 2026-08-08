"""Adzuna aggregator adapter (keyword + location search)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import structlog

from app.config import settings
from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery, register

log = structlog.get_logger(__name__)


@register
class AdzunaSource:
    name = JobSourceName.adzuna

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        if not (settings.adzuna_app_id and settings.adzuna_app_key):
            return  # no creds -> no-op (tests/dev use the fake source)
        country = settings.adzuna_country or "gb"
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": min(query.limit, 50),
            "max_days_old": 30,  # don't re-pull stale postings
        }
        # With specific ROLE TITLES (user search / target roles), use Adzuna's relevance
        # search (`what`) and let it rank by relevance — a role search wants the best match,
        # not the most recent "engineer" posting. Fall back to `what_or` + date-sort over
        # raw skills only when no role titles are set (AND-style `what` over many skills
        # returns almost nothing).
        if query.role_titles:
            terms = list(query.role_titles)
            if query.experience_level:
                terms = [f"{query.experience_level} {t}" for t in terms]
            params["what"] = " ".join(terms)
        else:
            terms = list(query.keywords) or [query.track.value]
            if query.experience_level:
                terms = [f"{query.experience_level} {t}" for t in terms]
            params["what_or"] = " ".join(terms)
            params["sort_by"] = "date"
        if query.location:
            params["where"] = query.location
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                log.warning("adzuna.http_error", status=exc.response.status_code,
                            body=exc.response.text[:300], country=country)
                # surface in the discover report (run_sources records the message)
                raise RuntimeError(
                    f"adzuna {exc.response.status_code}: {exc.response.text[:120]}"
                ) from exc
            except httpx.HTTPError as exc:
                log.warning("adzuna.request_failed", error=str(exc))
                raise RuntimeError(f"adzuna request failed: {exc}") from exc
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

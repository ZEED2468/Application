"""Deterministic fake source for dev + tests (no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.core.enums import JobSourceName, Track
from app.sources.base import RawJob, SourceQuery

_SAMPLES = {
    Track.frontend: [
        ("Acme Mobile", "Senior React Native Engineer", "Remote",
         "Build polished cross-platform mobile apps with React Native, animations and UI polish."),
        ("Pixelworks", "Frontend Engineer (React)", "Berlin",
         "Ship production web frontends in React + TypeScript with a focus on performance."),
    ],
    Track.backend: [
        ("Streamline", "Backend Engineer (Go)", "Remote",
         "Design and deploy production backend microservices in Go and NestJS, distributed systems."),
        ("DataForge", "Platform Engineer", "London",
         "Own infrastructure and backend services; Kubernetes, Postgres, event-driven systems."),
    ],
    Track.general: [
        ("Launchpad", "Full-Stack Software Engineer", "Remote",
         "Build complete products across the stack; solo end-to-end ownership, fast iteration."),
    ],
}


class FakeSource:
    name = JobSourceName.greenhouse  # tags jobs as a board source in dev

    def supports(self, track: Track) -> bool:
        return True

    async def fetch(self, query: SourceQuery) -> AsyncIterator[RawJob]:
        for i, (company, title, loc, desc) in enumerate(_SAMPLES.get(query.track, [])):
            yield RawJob(
                source=JobSourceName.greenhouse,
                source_job_id=f"fake-{query.track.value}-{i}",
                company=company,
                title=title,
                location=loc,
                url=f"https://example.com/jobs/{query.track.value}/{i}",
                description=desc,
                raw={"fake": True},
            )

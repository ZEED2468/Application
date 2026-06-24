"""Application + audit DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import ApplicationStatus, Origin, Track, TrackerStatus


class ApplicationOut(BaseModel):
    id: UUID
    job_id: UUID
    company: str | None
    role: str | None
    track: Track | None
    origin: Origin | None
    status: ApplicationStatus
    tracker_status: TrackerStatus
    submitted_at: datetime | None
    # VA-credibility signals (so a hunter can judge each application in-app).
    ats_score: float | None = None
    relevance_score: float | None = None
    va_name: str | None = None
    cv_url: str | None = None
    cover_url: str | None = None
    truthful: bool = False  # profile confirmed + truth-bounded generation

    @classmethod
    def from_models(cls, app, job, *, cv=None, cover=None, va_name=None,
                    truthful: bool = False) -> "ApplicationOut":
        return cls(
            id=app.id, job_id=app.job_id,
            company=job.company if job else None,
            role=(job.role_title or job.title) if job else None,
            track=job.track if job else None,
            origin=job.origin if job else None,
            status=app.status, tracker_status=app.tracker_status,
            submitted_at=app.submitted_at,
            ats_score=cv.ats_score if cv else None,
            relevance_score=job.relevance_score if job else None,
            va_name=va_name,
            cv_url=(f"/api/jobs/{app.job_id}/cv" if (cv and cv.pdf_key) else None),
            cover_url=(f"/api/jobs/{app.job_id}/cover" if (cover and cover.pdf_key) else None),
            truthful=truthful,
        )


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    actor: str
    detail: dict
    created_at: datetime

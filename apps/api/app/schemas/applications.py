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

    @classmethod
    def from_models(cls, app, job) -> "ApplicationOut":
        return cls(
            id=app.id, job_id=app.job_id,
            company=job.company if job else None,
            role=(job.role_title or job.title) if job else None,
            track=job.track if job else None,
            origin=job.origin if job else None,
            status=app.status, tracker_status=app.tracker_status,
            submitted_at=app.submitted_at,
        )


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    actor: str
    detail: dict
    created_at: datetime

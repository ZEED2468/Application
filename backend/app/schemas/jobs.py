"""Job + application DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import JobStatus, Track


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company: str
    title: str
    location: str | None
    url: str | None
    relevance_score: float | None
    track: Track | None
    track_override: Track | None
    status: JobStatus
    created_at: datetime


class TrackOverrideRequest(BaseModel):
    track: Track


class GenerateResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    generated_cv_id: UUID | None = None
    pdf_url: str | None = None


class SubmitResponse(BaseModel):
    application_id: UUID
    status: str

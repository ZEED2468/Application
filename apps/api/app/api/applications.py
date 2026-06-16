"""Applications API — the tracker status dropdown, audit trail, and xlsx export.

The dashboard is the single source of truth; export is one-way (never authoritative).
"""

from __future__ import annotations

import io
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TrackerStatus
from app.core.errors import NotFoundError
from app.db import get_session
from app.deps import current_user
from app.models.job import Job
from app.models.user import User
from app.repositories import applications as app_repo
from app.schemas.applications import ApplicationOut, AuditEventOut

router = APIRouter(tags=["applications"])


class StatusUpdate(BaseModel):
    status: TrackerStatus


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[ApplicationOut]:
    rows = await app_repo.list_for_user(session, user_id=user.id)
    out: list[ApplicationOut] = []
    for a in rows:
        job = await session.get(Job, a.job_id)
        out.append(ApplicationOut.from_models(a, job))
    return out


@router.patch("/applications/{application_id}/status", response_model=ApplicationOut)
async def update_status(
    application_id: UUID, body: StatusUpdate,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    app = await app_repo.get_owned(session, user_id=user.id, application_id=application_id)
    if app is None:
        raise NotFoundError("Application not found")
    await app_repo.set_tracker_status(
        session, application=app, status=body.status, actor=f"hunter:{user.id}"
    )
    job = await session.get(Job, app.job_id)
    return ApplicationOut.from_models(app, job)


@router.get("/applications/{application_id}/audit", response_model=list[AuditEventOut])
async def application_audit(
    application_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> list[AuditEventOut]:
    events = await app_repo.list_audit(session, user_id=user.id, application_id=application_id)
    return [AuditEventOut.model_validate(e) for e in events]


@router.get("/applications/export.xlsx")
async def export_xlsx(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> Response:
    """One-click spreadsheet export of the tracker (export-only)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(["Company", "Role", "Track", "Origin", "ATS", "Tracker Status",
               "Lifecycle", "Submitted At"])
    for a in await app_repo.list_for_user(session, user_id=user.id):
        job = await session.get(Job, a.job_id)
        from app.models.generated_cv import GeneratedCv
        cv = (await session.execute(
            select(GeneratedCv).where(GeneratedCv.job_id == a.job_id)
        )).scalar_one_or_none()
        ws.append([
            job.company if job else "", job.role_title or (job.title if job else ""),
            (job.track.value if job and job.track else ""),
            (job.origin.value if job else ""),
            (cv.ats_score if cv else ""), a.tracker_status.value, a.status.value,
            str(a.submitted_at or ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=applications.xlsx"},
    )

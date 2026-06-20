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

from app.core.enums import PrincipalType, TrackerStatus
from app.core.errors import ConflictError, NotFoundError
from app.db import get_session
from app.deps import Principal, authorize_owner, current_principal, scoped_user_ids
from app.models.application import Application
from app.models.job import Job
from app.repositories import applications as app_repo
from app.schemas.applications import ApplicationOut, AuditEventOut

router = APIRouter(tags=["applications"])


class StatusUpdate(BaseModel):
    status: TrackerStatus


def _actor(principal: Principal) -> str:
    kind = "va" if principal.type is PrincipalType.va else "hunter"
    return f"{kind}:{principal.id}"


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[ApplicationOut]:
    out: list[ApplicationOut] = []
    for uid in await scoped_user_ids(session, principal):
        for a in await app_repo.list_for_user(session, user_id=uid):
            job = await session.get(Job, a.job_id)
            out.append(ApplicationOut.from_models(a, job))
    out.sort(key=lambda o: str(o.submitted_at or ""), reverse=True)
    return out


@router.patch("/applications/{application_id}/status", response_model=ApplicationOut)
async def update_status(
    application_id: UUID, body: StatusUpdate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> ApplicationOut:
    app = await session.get(Application, application_id)
    if app is None:
        raise NotFoundError("Application not found")
    if body.status is TrackerStatus.not_applied:
        raise ConflictError(
            "not_applied is only shown for jobs that have not been submitted yet"
        )
    job = await session.get(Job, app.job_id)
    await authorize_owner(
        session, principal, app.user_id, track=job.track if job else None
    )
    await app_repo.set_tracker_status(
        session, application=app, status=body.status, actor=_actor(principal)
    )
    job = await session.get(Job, app.job_id)
    return ApplicationOut.from_models(app, job)


@router.get("/applications/{application_id}/audit", response_model=list[AuditEventOut])
async def application_audit(
    application_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[AuditEventOut]:
    app = await session.get(Application, application_id)
    if app is None:
        raise NotFoundError("Application not found")
    job = await session.get(Job, app.job_id)
    await authorize_owner(
        session, principal, app.user_id, track=job.track if job else None
    )
    events = await app_repo.list_audit(
        session, user_id=app.user_id, application_id=application_id
    )
    return [AuditEventOut.model_validate(e) for e in events]


@router.get("/applications/export.xlsx")
async def export_xlsx(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """One-click spreadsheet export of the tracker (export-only)."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(["Company", "Role", "Track", "Origin", "ATS", "Tracker Status",
               "Lifecycle", "Submitted At"])
    apps: list[Application] = []
    for uid in await scoped_user_ids(session, principal):
        apps.extend(await app_repo.list_for_user(session, user_id=uid))
    for a in apps:
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

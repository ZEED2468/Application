"""VA work queue: applications to submit, first-contact outreach to review, replies."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DossierStatus, JobStatus, OutreachStatus, PrincipalType, Track
from app.db import get_session
from app.deps import Principal, current_principal
from app.models.application import Application
from app.models.dossier import Dossier
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.thread import Thread
from app.models.user import User
from app.models.va_assignment import VaAssignment

router = APIRouter(prefix="/va", tags=["va"])


async def _scoped_user_ids(session: AsyncSession, principal: Principal) -> list:
    if principal.type is PrincipalType.user:
        return [principal.id]
    rows = (await session.execute(
        select(VaAssignment.user_id).where(VaAssignment.va_id == principal.id)
    )).scalars().all()
    return list(set(rows))


def _iso(dt) -> str:
    return dt.isoformat() if dt is not None else ""


@router.get("/queue")
async def queue(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Flat queue items matching the web app's `VaQueueItem` contract."""
    user_ids = await _scoped_user_ids(session, principal)
    if not user_ids:
        return []

    hunter_names = {
        u.id: u.name
        for u in (await session.execute(
            select(User).where(User.id.in_(user_ids))
        )).scalars().all()
    }

    items: list[dict] = []

    ready_jobs = (await session.execute(
        select(Job).where(Job.user_id.in_(user_ids), Job.status == JobStatus.ready)
    )).scalars().all()
    for job in ready_jobs:
        items.append({
            "id": str(job.id),
            "kind": "submit",
            "job_id": str(job.id),
            "company": job.company,
            "role": job.role_title or job.title,
            "hunter_name": hunter_names.get(job.user_id, ""),
            "track": (job.track or Track.general).value,
            "preview": None,
            "created_at": _iso(job.created_at),
        })

    reviews = (await session.execute(
        select(Outreach).where(
            Outreach.user_id.in_(user_ids), Outreach.status == OutreachStatus.review
        )
    )).scalars().all()
    for outreach in reviews:
        app = await session.get(Application, outreach.application_id)
        job = await session.get(Job, app.job_id) if app else None
        items.append({
            "id": str(outreach.id),
            "kind": "outreach_review",
            "job_id": str(job.id) if job else "",
            "company": job.company if job else "",
            "role": (job.role_title or job.title) if job else "",
            "hunter_name": hunter_names.get(outreach.user_id, ""),
            "track": ((job.track if job else None) or Track.general).value,
            "preview": outreach.subject or (outreach.body[:200] if outreach.body else None),
            "created_at": _iso(outreach.created_at),
        })

    dossiers = (await session.execute(
        select(Dossier).where(
            Dossier.user_id.in_(user_ids), Dossier.status == DossierStatus.pushed
        )
    )).scalars().all()
    for dossier in dossiers:
        thread = await session.get(Thread, dossier.thread_id)
        app = await session.get(Application, thread.application_id) if thread else None
        job = await session.get(Job, app.job_id) if app else None
        items.append({
            "id": str(dossier.id),
            "kind": "reply",
            "job_id": str(job.id) if job else "",
            "company": job.company if job else "",
            "role": (job.role_title or job.title) if job else "",
            "hunter_name": hunter_names.get(dossier.user_id, ""),
            "track": ((job.track if job else None) or Track.general).value,
            "preview": dossier.summary or dossier.suggested_reply,
            "created_at": _iso(dossier.pushed_at or dossier.created_at),
        })

    items.sort(key=lambda row: row["created_at"], reverse=True)
    return items

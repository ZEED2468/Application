"""VA work queue: applications to submit, first-contact outreach to review, replies."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import DossierStatus, JobStatus, OutreachStatus, PrincipalType
from app.db import get_session
from app.deps import Principal, current_principal
from app.models.application import Application
from app.models.dossier import Dossier
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.va_assignment import VaAssignment

router = APIRouter(prefix="/va", tags=["va"])


async def _scoped_user_ids(session: AsyncSession, principal: Principal) -> list:
    if principal.type is PrincipalType.user:
        return [principal.id]
    rows = (await session.execute(
        select(VaAssignment.user_id).where(VaAssignment.va_id == principal.id)
    )).scalars().all()
    return list(set(rows))


@router.get("/queue")
async def queue(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user_ids = await _scoped_user_ids(session, principal)
    if not user_ids:
        return {"to_submit": [], "outreach_review": [], "replies": []}

    ready_jobs = (await session.execute(
        select(Job).where(Job.user_id.in_(user_ids), Job.status == JobStatus.ready)
    )).scalars().all()
    to_submit = [{"job_id": str(j.id), "company": j.company,
                  "role": j.role_title or j.title, "track": j.track.value if j.track else None}
                 for j in ready_jobs]

    reviews = (await session.execute(
        select(Outreach).where(
            Outreach.user_id.in_(user_ids), Outreach.status == OutreachStatus.review
        )
    )).scalars().all()
    outreach_review = [{"outreach_id": str(o.id), "subject": o.subject,
                        "body": o.body, "application_id": str(o.application_id)}
                       for o in reviews]

    dossiers = (await session.execute(
        select(Dossier).where(
            Dossier.user_id.in_(user_ids), Dossier.status == DossierStatus.pushed
        )
    )).scalars().all()
    replies = [{"dossier_id": str(d.id), "summary": d.summary,
                "suggested_reply": d.suggested_reply} for d in dossiers]

    return {"to_submit": to_submit, "outreach_review": outreach_review, "replies": replies}

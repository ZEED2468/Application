"""Admin: 9-domain health panel + per-hunter weekly quota meter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import OutreachStatus
from app.db import get_session
from app.deps import require_admin
from app.models.outreach import Outreach
from app.models.user import User
from app.repositories import domains as domains_repo

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/domains")
async def domain_health(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> dict:
    domains = await domains_repo.list_all(session)
    return {
        "domains": [
            {
                "id": str(d.id), "user_id": str(d.user_id), "track": d.track.value,
                "domain": d.domain, "warmup_stage": d.warmup_stage.value,
                "daily_sent": d.daily_sent_count, "is_paused": d.is_paused,
                "pause_reason": d.pause_reason,
                "bounce_rate": d.bounce_rate, "complaint_rate": d.complaint_rate,
                "dkim": d.dkim_status.value, "spf": d.spf_status.value,
                "dmarc": d.dmarc_status.value,
            }
            for d in domains
        ]
    }


@router.get("/quota")
async def quota(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    hunters = (await session.execute(select(User))).scalars().all()
    out = []
    for u in hunters:
        sent = (await session.execute(
            select(func.count()).select_from(Outreach).where(
                Outreach.user_id == u.id, Outreach.status == OutreachStatus.sent,
                Outreach.sent_at >= since,
            )
        )).scalar_one()
        out.append({"user_id": str(u.id), "name": u.name,
                    "sent_last_7d": int(sent), "weekly_cap": settings.weekly_cap_per_hunter})
    return {"hunters": out}

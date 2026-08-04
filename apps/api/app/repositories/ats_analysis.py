"""Persistence for ATS check results (`ats_analysis`).

Append-only history: each check records a new row; the newest row for a
`(user, job)` pair (job may be NULL for a standalone check) is the current analysis.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ats_analysis import AtsAnalysis


async def record(
    session: AsyncSession,
    *,
    user_id,
    job_id,
    track: str | None,
    role_title: str | None,
    gate_status: str,
    score: float | None,
    breakdown: dict,
    ai: dict | None,
    ai_live: bool,
) -> AtsAnalysis:
    # Monotonic per (user, job) run counter — newest = current.
    prior = (await session.execute(
        select(func.count()).select_from(AtsAnalysis).where(
            AtsAnalysis.user_id == user_id, AtsAnalysis.job_id == job_id
        )
    )).scalar_one()
    row = AtsAnalysis(
        user_id=user_id, job_id=job_id, track=track, role_title=role_title,
        gate_status=gate_status, score=score, breakdown=breakdown or {},
        ai=ai, ai_live=ai_live, version=int(prior) + 1,
    )
    session.add(row)
    await session.flush()
    return row


async def latest(session: AsyncSession, *, user_id, job_id) -> AtsAnalysis | None:
    return (await session.execute(
        select(AtsAnalysis)
        .where(AtsAnalysis.user_id == user_id, AtsAnalysis.job_id == job_id)
        .order_by(AtsAnalysis.created_at.desc(), AtsAnalysis.version.desc())
        .limit(1)
    )).scalars().first()

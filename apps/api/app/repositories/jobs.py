"""Job data access. All queries require user_id — no implicit all-users reads."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import JobStatus
from app.models.job import Job


async def insert_if_new(session: AsyncSession, *, user_id: UUID, fields: dict) -> Job | None:
    """Insert a job; return it if newly created, else None on dedupe collision.

    Portable across Postgres/SQLite via a SAVEPOINT + IntegrityError catch on the
    `(user_id, dedupe_key)` unique constraint.
    """
    job = Job(user_id=user_id, **fields)
    try:
        # Add inside the SAVEPOINT so a dedupe collision rolls the object back
        # out of the session instead of poisoning the outer transaction.
        async with session.begin_nested():
            session.add(job)
            await session.flush()
    except IntegrityError:
        return None
    return job


async def list_for_user(
    session: AsyncSession, *, user_id: UUID, status: JobStatus | None = None
) -> list[Job]:
    stmt = select(Job).where(Job.user_id == user_id)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    stmt = stmt.order_by(Job.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_owned(session: AsyncSession, *, user_id: UUID, job_id: UUID) -> Job | None:
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user_id:
        return None
    return job

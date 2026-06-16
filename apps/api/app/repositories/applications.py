"""application access + the audit trail. Both pipelines converge here."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import TrackerStatus
from app.models.application import Application
from app.models.application_event import ApplicationEvent


async def get_owned(
    session: AsyncSession, *, user_id: UUID, application_id: UUID
) -> Application | None:
    app = await session.get(Application, application_id)
    if app is None or app.user_id != user_id:
        return None
    return app


async def list_for_user(session: AsyncSession, *, user_id: UUID) -> list[Application]:
    stmt = (
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


def record_event(
    session: AsyncSession, *, application: Application, kind: str,
    actor: str = "system", detail: dict | None = None,
) -> ApplicationEvent:
    """Append an audit-trail row. Caller flushes/commits."""
    event = ApplicationEvent(
        user_id=application.user_id, application_id=application.id,
        kind=kind, actor=actor, detail=detail or {},
    )
    session.add(event)
    return event


async def set_tracker_status(
    session: AsyncSession, *, application: Application, status: TrackerStatus, actor: str
) -> Application:
    old = application.tracker_status
    application.tracker_status = status
    record_event(
        session, application=application, kind="status_changed", actor=actor,
        detail={"from": old.value, "to": status.value},
    )
    await session.flush()
    return application


async def list_audit(
    session: AsyncSession, *, user_id: UUID, application_id: UUID
) -> list[ApplicationEvent]:
    stmt = (
        select(ApplicationEvent)
        .where(
            ApplicationEvent.application_id == application_id,
            ApplicationEvent.user_id == user_id,
        )
        .order_by(ApplicationEvent.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())

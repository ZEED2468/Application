"""Run an async coroutine inside a sync Celery task with a fresh DB session."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.db import AsyncSessionLocal

T = TypeVar("T")


def run_with_session(fn: Callable[..., Awaitable[T]]) -> T:
    """Open a session, run `fn(session)`, commit on success / rollback on error."""

    async def _run() -> T:
        async with AsyncSessionLocal() as session:
            try:
                result = await fn(session)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

    return asyncio.run(_run())

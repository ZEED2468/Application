"""Per-(user, source, query) discovery cooldown.

Skips a redundant Adzuna/SerpApi call when the *same* query already ran within the
cooldown window (`settings.discover_cooldown_seconds`), so the 30-min beat + on-demand
runs don't re-fetch identical results and burn API tokens. Fails **open** — any Redis
problem (or fake mode) means "don't skip", so discovery is never blocked by the cache.
"""

from __future__ import annotations

import hashlib

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


def query_hash(source: str, query) -> str:
    track = query.track.value if hasattr(query.track, "value") else str(query.track)
    basis = "|".join([
        source, track,
        ",".join(sorted(query.keywords or [])),
        ",".join(sorted(query.role_titles or [])),
        ",".join(sorted(query.boards or [])),  # a new company board must bust the cooldown
        query.location or "",
        query.experience_level or "",
    ])
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def _enabled() -> bool:
    return not settings.use_fake_integrations and settings.discover_cooldown_seconds > 0


def _key(user_id, source: str, qhash: str) -> str:
    return f"discover:cd:{user_id}:{source}:{qhash}"


async def should_skip(user_id, source: str, qhash: str) -> bool:
    """True if this exact query was fetched within the cooldown window."""
    if not _enabled():
        return False
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        try:
            return bool(await client.exists(_key(user_id, source, qhash)))
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001 — fail open; never block discovery
        log.warning("discover.cooldown_check_failed", error=str(exc))
        return False


async def mark_ran(user_id, source: str, qhash: str) -> None:
    if not _enabled():
        return
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.redis_url)
        try:
            await client.setex(_key(user_id, source, qhash), settings.discover_cooldown_seconds, "1")
        finally:
            await client.aclose()
    except Exception as exc:  # noqa: BLE001
        log.warning("discover.cooldown_mark_failed", error=str(exc))

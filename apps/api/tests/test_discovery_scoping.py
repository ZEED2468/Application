"""Discovery scopes the outbound Adzuna/SerpApi query by the hunter's filters (role
titles, location, seniority) so providers return only relevant postings — and the
per-query cooldown hash is stable/changing as expected (saves API tokens)."""

from __future__ import annotations

import httpx
import pytest

from app.config import settings
from app.core.enums import Track
from app.pipelines.apply import discover_cache
from app.sources.adzuna import AdzunaSource
from app.sources.base import SourceQuery
from app.sources.serpapi_jobs import SerpApiSource


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def _capture_get(monkeypatch, payload):
    captured: dict = {}

    async def fake_get(self, url, params=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResp(payload)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    return captured


@pytest.mark.asyncio
async def test_adzuna_scoped_by_roles_location_experience(monkeypatch):
    monkeypatch.setattr(settings, "adzuna_app_id", "id")
    monkeypatch.setattr(settings, "adzuna_app_key", "key")
    cap = _capture_get(monkeypatch, {"results": []})
    q = SourceQuery(track=Track.backend, keywords=["go", "kafka"],
                    role_titles=["Backend Engineer"], location="Berlin",
                    experience_level="senior")
    async for _ in AdzunaSource().fetch(q):
        pass
    p = cap["params"]
    # role titles → Adzuna relevance search (`what`, not `what_or`), seniority folded in,
    # location -> where, recency cap; skills are NOT used when role titles are present.
    assert "backend engineer" in p["what"].lower()
    assert "senior" in p["what"].lower()
    assert "what_or" not in p  # role path uses relevance `what`, not the skills `what_or`
    assert p["where"] == "Berlin"
    assert p["max_days_old"] == 30


@pytest.mark.asyncio
async def test_serpapi_scoped_by_experience_and_location(monkeypatch):
    monkeypatch.setattr(settings, "serpapi_api_key", "k")
    cap = _capture_get(monkeypatch, {"jobs_results": []})
    q = SourceQuery(track=Track.frontend, role_titles=["React Engineer"],
                    location="Lagos", experience_level="junior")
    async for _ in SerpApiSource().fetch(q):
        pass
    p = cap["params"]
    assert "react engineer" in p["q"].lower()
    assert p["q"].lower().startswith("junior")
    assert p["location"] == "Lagos"


def test_query_hash_stable_and_sensitive():
    base = SourceQuery(track=Track.backend, keywords=["go"], role_titles=["Backend Engineer"],
                       location="Berlin", experience_level="senior")
    same = SourceQuery(track=Track.backend, keywords=["go"], role_titles=["Backend Engineer"],
                       location="Berlin", experience_level="senior")
    assert discover_cache.query_hash("adzuna", base) == discover_cache.query_hash("adzuna", same)
    # a changed filter -> different hash (so a new query bypasses the cooldown)
    changed = SourceQuery(track=Track.backend, keywords=["go"], role_titles=["Backend Engineer"],
                          location="Munich", experience_level="senior")
    assert discover_cache.query_hash("adzuna", base) != discover_cache.query_hash("adzuna", changed)
    # different source -> different key namespace
    assert discover_cache.query_hash("adzuna", base) != discover_cache.query_hash("serpapi", base)


@pytest.mark.asyncio
async def test_serpapi_parenthesizes_role_title_or_group(monkeypatch):
    # Multiple target roles must be OR'd inside a parenthesized group so the
    # seniority/remote qualifiers bind to *all* titles, not just the first/last.
    monkeypatch.setattr(settings, "serpapi_api_key", "k")
    cap = _capture_get(monkeypatch, {"jobs_results": []})
    q = SourceQuery(track=Track.frontend,
                    role_titles=["React Engineer", "Frontend Engineer"],
                    experience_level="senior")
    async for _ in SerpApiSource().fetch(q):
        pass
    qstr = cap["params"]["q"].lower()
    assert "(react engineer or frontend engineer)" in qstr
    assert qstr.startswith("senior (")  # seniority prefix binds to the whole group
    assert qstr.endswith(")remote") or qstr.endswith(") remote")  # remote appended after the group


def test_query_hash_includes_boards():
    # Adding/removing a company board must bust the cooldown so the new board is fetched.
    base = SourceQuery(track=Track.backend, role_titles=["Backend Engineer"], boards=["acme"])
    more = SourceQuery(track=Track.backend, role_titles=["Backend Engineer"],
                       boards=["acme", "globex"])
    assert discover_cache.query_hash("greenhouse", base) != discover_cache.query_hash("greenhouse", more)
    # order-insensitive (boards are sorted before hashing)
    reordered = SourceQuery(track=Track.backend, role_titles=["Backend Engineer"],
                            boards=["globex", "acme"])
    assert discover_cache.query_hash("greenhouse", more) == discover_cache.query_hash("greenhouse", reordered)


@pytest.mark.asyncio
async def test_cooldown_disabled_in_fake_mode():
    # fake mode -> cooldown never blocks discovery (fail-open)
    assert settings.use_fake_integrations is True
    assert await discover_cache.should_skip("u1", "adzuna", "abc") is False
    await discover_cache.mark_ran("u1", "adzuna", "abc")  # no-op, no Redis needed

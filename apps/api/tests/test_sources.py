"""Source normalization + the fake source + dedupe-aware insert + board tokens."""

import pytest

from app.core.enums import JobSourceName, Track
from app.core.ids import new_id
from app.pipelines.apply import service
from app.repositories import jobs as jobs_repo
from app.repositories import source_boards as boards_repo
from app.sources.base import RawJob, SourceQuery
from app.sources.fake import FakeSource
from app.sources.normalize import dedupe_key, to_job_fields
from tests.helpers import EventSink, seed_hunter


def _raw(company="Acme", title="Backend Engineer", location="Remote"):
    return RawJob(
        source=JobSourceName.greenhouse, source_job_id="1",
        company=company, title=title, location=location,
    )


def test_dedupe_key_is_stable_and_case_insensitive():
    a = dedupe_key(_raw(company="Acme", title="Backend Engineer"))
    b = dedupe_key(_raw(company="  acme ", title="BACKEND   engineer"))
    c = dedupe_key(_raw(company="Other"))
    assert a == b
    assert a != c


@pytest.mark.asyncio
async def test_fake_source_yields_per_track():
    src = FakeSource()
    jobs = [j async for j in src.fetch(SourceQuery(track=Track.backend))]
    assert jobs and all(j.title for j in jobs)


@pytest.mark.asyncio
async def test_insert_if_new_dedupes_per_hunter(session):
    user_id = new_id()
    fields = to_job_fields(_raw())
    first = await jobs_repo.insert_if_new(session, user_id=user_id, fields=fields)
    dup = await jobs_repo.insert_if_new(session, user_id=user_id, fields=fields)
    assert first is not None
    assert dup is None  # same hunter + dedupe_key -> collapsed

    other = await jobs_repo.insert_if_new(session, user_id=new_id(), fields=fields)
    assert other is not None  # different hunter -> allowed


@pytest.mark.asyncio
async def test_source_boards_active_by_source_groups(session):
    await boards_repo.create(session, source=JobSourceName.greenhouse, token="airbnb", label="Airbnb")
    await boards_repo.create(session, source=JobSourceName.greenhouse, token="stripe", label=None)
    await boards_repo.create(session, source=JobSourceName.lever, token="netflix", label=None)
    inactive = await boards_repo.create(session, source=JobSourceName.lever, token="dead", label=None)
    inactive.is_active = False
    await session.flush()

    grouped = await boards_repo.active_by_source(session)
    assert set(grouped[JobSourceName.greenhouse]) == {"airbnb", "stripe"}
    assert grouped[JobSourceName.lever] == ["netflix"]  # inactive excluded


class _RecordingSource:
    """A board source that records the tokens it was handed."""

    name = JobSourceName.greenhouse

    def __init__(self):
        self.seen: list[str] = []

    def supports(self, track):
        return True

    async def fetch(self, query):
        self.seen = list(query.boards)
        return
        yield  # unreachable — marks this as an async generator


@pytest.mark.asyncio
async def test_discover_passes_per_source_board_tokens(session, monkeypatch):
    user, profile = await seed_hunter(session)
    await boards_repo.create(session, source=JobSourceName.greenhouse, token="airbnb", label=None)
    await boards_repo.create(session, source=JobSourceName.lever, token="netflix", label=None)

    rec = _RecordingSource()
    monkeypatch.setattr(service, "active_sources", lambda: [rec])
    await service.discover_for_user(session, user_id=user.id, profile=profile, emit=EventSink())

    # the greenhouse source receives only greenhouse tokens, not lever's
    assert rec.seen == ["airbnb"]


def test_title_matches_roles():
    assert service.title_matches_roles("Senior React Engineer (Remote)", ["React Engineer"])
    assert service.title_matches_roles("Backend Engineer", [])  # no roles -> match all
    assert not service.title_matches_roles(
        "Product Manager", ["React Engineer", "Frontend Engineer"]
    )


class _TwoJobSource:
    name = JobSourceName.serpapi

    def supports(self, track):
        return True

    async def fetch(self, query):
        yield RawJob(source=self.name, source_job_id="1", company="A",
                     title="Senior React Engineer", location="Remote")
        yield RawJob(source=self.name, source_job_id="2", company="B",
                     title="Product Manager", location="Remote")


@pytest.mark.asyncio
async def test_discovery_filters_off_target_roles(session, monkeypatch):
    user, profile = await seed_hunter(session)
    profile.target_roles = ["React Engineer"]
    await session.flush()

    monkeypatch.setattr(service, "active_sources", lambda: [_TwoJobSource()])
    new_jobs, report = await service._run_sources(
        session, user_id=user.id, profile=profile, emit=EventSink()
    )

    assert [j.title for j in new_jobs] == ["Senior React Engineer"]  # PM dropped
    assert new_jobs[0].role_title == "Senior React Engineer"
    assert report[0]["off_target"] == 1 and report[0]["inserted"] == 1


@pytest.mark.asyncio
async def test_run_sources_returns_per_source_report(session):
    user, profile = await seed_hunter(session)
    new_jobs, report = await service._run_sources(
        session, user_id=user.id, profile=profile, emit=EventSink()
    )
    assert new_jobs  # fake source yields jobs in test mode
    assert report and all(
        {"source", "found", "inserted", "error"} <= r.keys() for r in report
    )
    assert sum(r["inserted"] for r in report) == len(new_jobs)


@pytest.mark.asyncio
async def test_discovery_resilient_to_board_lookup_failure(session, monkeypatch):
    user, profile = await seed_hunter(session)

    async def _boom(_session):
        raise RuntimeError("source_board table missing")

    monkeypatch.setattr(boards_repo, "active_by_source", _boom)
    # must NOT raise — a missing/un-migrated source_board table degrades gracefully
    new_jobs, report = await service._run_sources(
        session, user_id=user.id, profile=profile, emit=EventSink()
    )
    assert report  # sources still ran despite the board lookup failing

"""Source normalization + the fake source + dedupe-aware insert."""

import pytest

from app.core.enums import JobSourceName, Track
from app.core.ids import new_id
from app.repositories import jobs as jobs_repo
from app.sources.base import RawJob, SourceQuery
from app.sources.fake import FakeSource
from app.sources.normalize import dedupe_key, to_job_fields


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

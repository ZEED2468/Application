"""Slice 9: the CV engine finishes every generated CV.

generation hands tailoring's output to the engine, which grounds it against the candidate's REAL
profile (an independent ledger) and persists its verified output as the GeneratedCv. A tailored CV
that invents an employer the profile lacks is caught by grounding → it is never marked ready.
"""

from sqlalchemy import select

from app.core.enums import JobSourceName, Origin, RunState, Track, UserRole
from app.cv_engine.runs.models import CvRun
from app.llm import tailoring
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines import generation
from app.security import hash_password


async def _seed(session):
    user = User(email="s9@example.com", password_hash=hash_password("x"),
                name="Ada Hunter", role=UserRole.hunter)
    session.add(user)
    await session.flush()
    profile = MasterProfile(
        user_id=user.id, track=Track.backend, headline="Backend engineer",
        summary="Backend engineer building production systems.",
        skills=["Go", "Kubernetes", "Postgres"],
        experience=[{"title": "Backend Engineer", "company": "Streamline",
                     "bullets": ["Built Go microservices"]}],
        projects=[], education=[], links={"github": "https://github.com/adahunter"},
    )
    session.add(profile)
    await session.flush()
    job = Job(user_id=user.id, source=JobSourceName.manual, origin=Origin.manual,
              dedupe_key="dk-s9", company="Acme", title="Backend Engineer",
              role_title="Backend Engineer", description="Backend role using Go and Kubernetes.",
              track=Track.backend)
    session.add(job)
    await session.flush()
    return user, profile, job


async def test_engine_is_the_cv_finisher(session):
    user, profile, job = await _seed(session)
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=user, emit=lambda *a, **k: None)

    run = (await session.execute(select(CvRun).where(CvRun.job_id == job.id))).scalar_one()
    # The GeneratedCv is sourced from the engine's verified output, not a separate render.
    assert cv.tailoring_diff["engine"]["run_id"] == str(run.id)
    assert run.result_cv_json is not None and cv.cv_json == run.result_cv_json
    assert run.tex and cv.latex_source == run.tex


async def test_grounding_catches_a_fabricated_employer(session, monkeypatch):
    user, profile, job = await _seed(session)

    async def _fabricate(profile_dict, **k):
        # Invent an employer the profile never had — the engine must catch it.
        return {
            "headline": "Backend Engineer", "summary": "Backend engineer building systems.",
            "skills": ["Go", "Kubernetes"],
            "experience": [{"title": "Engineer", "company": "Nonexistent Fabrications Incorporated",
                            "dates": "2020 -- 2024", "bullets": ["Built Go services"]}],
            "links": {"github": "https://github.com/adahunter"},
        }, {}

    monkeypatch.setattr(tailoring, "tailor", _fabricate)
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=user, emit=lambda *a, **k: None)

    run = (await session.execute(select(CvRun).where(CvRun.job_id == job.id))).scalar_one()
    # The engine's grounding seal (against the real profile ledger) flags the invented employer,
    # so the run never releases — the verification the live tailoring path lacked. (In real mode
    # this makes GeneratedCv.status=failed; fake/dev mode keeps the stub-render convenience.)
    assert run.state is RunState.needs_review
    assert any(v["rule_id"].startswith("grounding.") for v in run.violations)


async def test_priority_techs_excludes_unowned_criticals(session, monkeypatch):
    # We used to feed EVERY JD must-have to tailoring as a "priority tech to emphasize" — including
    # ones the profile lacks — which is exactly what makes a live model fabricate them. Only owned
    # criticals may be emphasized; the rest are the JD gaps the engine asks about (never invented).
    user, profile, job = await _seed(session)
    job.description = "Backend Engineer. Kafka is required. Strong Go experience is essential."
    captured: dict = {}

    async def _capture(profile_dict, *, priority_techs, **k):
        captured["priority_techs"] = priority_techs
        return {
            "summary": "Backend engineer building production systems.",
            "skills": ["Go", "Kubernetes"],
            "experience": [{"title": "Backend Engineer", "company": "Streamline",
                            "bullets": ["Built Go microservices"]}],
            "links": {"github": "https://github.com/adahunter"},
        }, {}

    monkeypatch.setattr(tailoring, "tailor", _capture)
    await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=user, emit=lambda *a, **k: None)

    pt = {p.lower() for p in captured["priority_techs"]}
    assert "go" in pt              # owned critical → still emphasized
    assert "kafka" not in pt       # un-owned critical → filtered out, never handed to the model

"""CV-engine runs — the deterministic spine + PATCH (format fixes), scored on a real artifact.

`POST /cv/runs` drives a raw cv_json + JD through the engine (standalone smoke surface).
`POST /cv/runs/job/{job_id}` runs it for a job (workspace "Check / fix format").
`POST /cv/runs/revamp/track/{track}` parses the uploaded source CV and re-renders it clean
(the "revamp my CV" flow); `GET /cv/runs/{id}/artifact` streams the resulting PDF.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tracks import assert_track_generatable
from app.core.enums import RunMode, Track
from app.core.errors import DomainError, NotFoundError
from app.cv_engine.ingest import parse_cv_text
from app.cv_engine.ingest.normalize import normalize_text
from app.cv_engine.runs.machine import run_pipeline
from app.cv_engine.runs.models import CvRun
from app.db import get_session
from app.deps import Principal, authorize_owner, current_principal, current_user
from app.integrations import r2
from app.llm.tailoring import _flatten_skills
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.pipelines.apply.cv_parse import extract_text_from_bytes
from app.pipelines.generation import enrich_from_verified_extras
from app.repositories import profiles as profiles_repo

router = APIRouter(prefix="/cv", tags=["cv"])


def run_to_dict(run: CvRun) -> dict:
    """The CvRunResult contract shared by the endpoints + the job detail."""
    return {
        "run_id": str(run.id),
        "state": run.state.value,
        "score": run.score,
        "registry_version": run.registry_version,
        "template": {"id": run.template_id, "version": run.template_version},
        "artifact_ref": run.artifact_ref,
        "violations": run.violations,
        "delta": run.delta,
        "judgment": run.judgment,
        "needs_input": run.needs_input,
    }


def _fresh_cv_json(profile: MasterProfile) -> dict:
    """The candidate's CV as-is (untailored): profile fields, skills flattened to a list,
    verified extras promoted to real sections. This is what the engine diagnoses + fixes."""
    profile_dict = profiles_repo.profile_to_dict(profile)
    cv_json = dict(profile_dict)
    cv_json["skills"] = _flatten_skills(cv_json.get("skills"))
    return enrich_from_verified_extras(cv_json, profile_dict)


class RunRequest(BaseModel):
    cv_json: dict = Field(..., description="Structured CV: summary, skills, experience, …")
    jd_text: str = Field("", description="Job description text (optional).")
    role_title: str | None = None
    track: str | None = None
    # Independent truth source; when omitted the ledger is derived from cv_json.
    ledger: list | None = None
    name: str | None = Field(None, description="Candidate name (defaults to the account name).")


@router.post("/runs", summary="Run a raw cv_json through the deterministic engine")
async def create_cv_run(
    body: RunRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await run_pipeline(
        session, user_id=user.id,
        input={
            "cv_json": body.cv_json,
            "jd_text": body.jd_text,
            "role_title": body.role_title,
            "track": body.track,
            "name": body.name or user.name,
            **({"ledger": body.ledger} if body.ledger is not None else {}),
        },
    )
    return run_to_dict(run)


@router.post("/runs/job/{job_id}", summary="Run the engine for a job (format check + fixes)")
async def create_cv_run_for_job(
    job_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    await authorize_owner(session, principal, job.user_id, track=job.track)
    # Same gate as generation — a track without a real, parsed source CV can't be checked.
    await assert_track_generatable(session, job.user_id, job.track)

    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == job.user_id, MasterProfile.track == job.track
        )
    )).scalar_one()
    owner = await session.get(User, job.user_id)

    run = await run_pipeline(
        session, user_id=job.user_id, job_id=job.id,
        input={
            "cv_json": _fresh_cv_json(profile),
            "jd_text": job.description or "",
            "role_title": job.role_title or job.title,
            "track": job.track.value if job.track else None,
            "name": owner.name if owner else "",
        },
    )
    return run_to_dict(run)


@router.post("/runs/revamp/track/{track}", summary="Revamp a track's uploaded CV")
async def revamp_track_cv(
    track: Track,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Parse the track's stored source CV deterministically, then re-render it through the
    canonical template (dates normalized, single-column, ATS-safe). The uploaded text is the
    independent ledger, so grounding is principled."""
    role_cv = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == track)
    )).scalar_one_or_none()
    if role_cv is None or not role_cv.source_file_key:
        raise NotFoundError("No source CV on file for this track — upload one first.")
    data = await r2.get_bytes(role_cv.source_file_key)
    if not data:
        raise NotFoundError("The stored CV file could not be retrieved.")

    text = extract_text_from_bytes(role_cv.original_filename or "", data)
    parsed = parse_cv_text(text)
    if parsed.scanned:
        raise DomainError(
            "We can't read this CV yet — it looks scanned/image-only. Upload a text-based "
            "PDF or DOCX so we can rebuild it.",
            code="cv_unreadable", title="Can't read this CV",
        )
    if not parsed.is_cv:
        raise DomainError(
            "This file doesn't look like a CV, so there's nothing to rebuild.",
            code="not_a_cv", title="Not a CV",
        )

    run = await run_pipeline(
        session, user_id=user.id, mode=RunMode.revamp,
        input={
            "cv_json": parsed.cv_json,
            "ledger": [{"kind": "upload", "source": "upload", "text": normalize_text(text)}],
            "jd_text": "", "role_title": None,
            "track": track.value, "name": user.name,
        },
    )
    return {**run_to_dict(run), "parse": {"confidence": parsed.confidence, "flags": parsed.flags}}


@router.get("/runs/{run_id}/artifact", summary="Download a run's compiled PDF")
async def download_run_artifact(
    run_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    run = await session.get(CvRun, run_id)
    if run is None:
        raise NotFoundError("Run not found")
    await authorize_owner(session, principal, run.user_id)
    if not run.artifact_ref:
        raise NotFoundError("This run has no compiled artifact.")
    pdf = await r2.get_bytes(run.artifact_ref)
    if not pdf:
        raise NotFoundError("The artifact could not be retrieved.")
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="cv.pdf"'},
    )

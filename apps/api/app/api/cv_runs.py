"""CV-engine runs — the deterministic spine + PATCH (format fixes), scored on a real artifact.

`POST /cv/runs` drives a raw cv_json + JD through the engine (standalone smoke surface).
`POST /cv/runs/job/{job_id}` runs it for a job: builds the fresh-build cv_json from the
track profile, applies deterministic fixes, and returns the terminal state, the score
computed on the compiled artifact, the violations, and the what-got-fixed delta — the
workspace "Check / fix format" action.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tracks import assert_track_generatable
from app.core.errors import NotFoundError
from app.cv_engine.runs.machine import run_pipeline
from app.cv_engine.runs.models import CvRun
from app.db import get_session
from app.deps import Principal, authorize_owner, current_principal, current_user
from app.llm.tailoring import _flatten_skills
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
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

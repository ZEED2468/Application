"""Internal CV-engine runs endpoint — Slice 1 smoke surface (not wired into the web UI).

`POST /cv/runs` drives a cv_json + JD through the deterministic spine and returns the
terminal state, the score computed on the real compiled artifact, and the violation set.
The next section wires this behind a visible screen; for now it exists so the closed
loop can be exercised end to end against a live server.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.cv_engine.runs.machine import run_pipeline
from app.db import get_session
from app.deps import current_user
from app.models.user import User

router = APIRouter(prefix="/cv", tags=["cv"])


class RunRequest(BaseModel):
    cv_json: dict = Field(..., description="Structured CV: summary, skills, experience, …")
    jd_text: str = Field("", description="Job description text (optional).")
    role_title: str | None = None
    track: str | None = None
    # Independent truth source; when omitted the ledger is derived from cv_json.
    ledger: list | None = None
    name: str | None = Field(None, description="Candidate name (defaults to the account name).")


@router.post("/runs", summary="Run a CV through the deterministic engine spine")
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

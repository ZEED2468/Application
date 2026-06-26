"""LaTeX API — stateless compile preview + draft regeneration from ATS recommendations.

`/preview` compiles editor LaTeX to an inline PDF (for the side-by-side builder).
`/regenerate` produces DRAFT tailored CV + cover LaTeX in the hunter's own template,
truth-bounded via `tailoring.tailor` / `generate_cover_letter`. Neither binds to a job;
"Use this template" (jobs.py `*/from-latex`) is what commits the result to a job.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import LatexKind, PrincipalType, Track
from app.core.errors import DomainError, ForbiddenError, NotFoundError
from app.db import get_session
from app.deps import Principal, authorize_owner, current_principal
from app.llm import cover_letter as cl
from app.llm import hookfinder
from app.models.cover_letter import CoverLetterTemplate
from app.models.job import Job
from app.models.latex_template import LatexTemplate
from app.models.user import User
from app.pipelines.apply import ats, latex_regen, render
from app.pipelines.apply.latex_safety import assert_safe
from app.repositories import profiles as profiles_repo

router = APIRouter(prefix="/latex", tags=["latex"])
log = structlog.get_logger(__name__)


class PreviewBody(BaseModel):
    latex: str
    kind: LatexKind = LatexKind.cv


class AtsRecs(BaseModel):
    missing_critical: list[str] = []
    gaps: list[str] = []
    ai_recommendations: list[str] = []


class RegenerateBody(BaseModel):
    job_id: UUID | None = None
    track: Track | None = None
    jd_text: str | None = None
    role_title: str | None = None
    ats: AtsRecs = AtsRecs()
    priority_techs: list[str] | None = None


@router.post("/preview")
async def preview(
    body: PreviewBody,
    principal: Principal = Depends(current_principal),
):
    """Compile editor LaTeX to an inline PDF. 400 if it contains forbidden
    primitives; 422 (with tectonic stderr) if it does not compile."""
    assert_safe(body.latex)  # DomainError -> 400 listing the rejected commands
    pdf, stderr = await render.render_pdf_checked(body.latex)
    if pdf is None:
        return JSONResponse(
            status_code=422, content={"error": "compile_failed", "stderr": stderr[:4000]}
        )
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="preview.pdf"'},
    )


async def _latex_source(session, user_id, track: Track, kind: LatexKind) -> str | None:
    lt = (await session.execute(
        select(LatexTemplate).where(
            LatexTemplate.user_id == user_id,
            LatexTemplate.track == track,
            LatexTemplate.kind == kind,
        )
    )).scalar_one_or_none()
    return lt.source if lt else None


@router.post("/regenerate")
async def regenerate(
    body: RegenerateBody,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Draft a tailored CV + cover letter in the hunter's LaTeX template, guided by
    the ATS recommendations. Returns LaTeX only — preview/commit happen separately."""
    track = body.track
    jd_text = body.jd_text
    role_title = body.role_title
    company = "the company"

    if body.job_id is not None:
        job = await session.get(Job, body.job_id)
        if job is None:
            raise NotFoundError("Job not found")
        await authorize_owner(session, principal, job.user_id, track=job.track)
        owner_id = job.user_id
        track = track or job.track
        jd_text = jd_text or job.description
        role_title = role_title or job.role_title or job.title
        company = job.company or company
    else:
        if principal.type is not PrincipalType.user:
            raise ForbiddenError("Pick a job to regenerate for.")
        owner_id = principal.id

    if track is None:
        raise DomainError("A track is required to regenerate.")

    owner = await session.get(User, owner_id)
    profile = await profiles_repo.get_by_user_track(session, user_id=owner_id, track=track)
    if profile is None:
        raise DomainError(f"No master profile for track '{track.value}'. Upload a source CV first.")
    profile_dict = profiles_repo.profile_to_dict(profile)

    priority_techs = body.priority_techs or ats.critical_keywords(jd_text or "")
    cv_template = await _latex_source(session, owner_id, track, LatexKind.cv)
    cover_template = await _latex_source(session, owner_id, track, LatexKind.cover)

    cv_res = await latex_regen.regenerate_cv_latex(
        template_tex=cv_template, profile_dict=profile_dict, owner_name=owner.name,
        job_title=role_title or "the role", jd_text=jd_text,
        ats_recs=body.ats.model_dump(), priority_techs=priority_techs,
    )

    tone = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == owner_id)
    )).scalar_one_or_none()
    hook = await hookfinder.find_hook(company=company, track=track, job_description=jd_text)
    cl_body = await cl.generate_cover_letter(
        candidate_name=owner.name, company=company, role_title=role_title or "the role",
        track=track, hook=hook, profile=profile_dict, jd_text=jd_text,
        template_body=tone.body if tone else None,
    )
    cover_res = await latex_regen.regenerate_cover_latex(
        template_tex=cover_template, cl_body=cl_body, owner_name=owner.name,
        company=company, role_title=role_title or "the role",
    )

    log.info("latex.regenerate", user_id=str(owner_id), track=track.value,
             cv_fell_back=cv_res.fell_back, cover_fell_back=cover_res.fell_back)
    return {
        "cv_latex": cv_res.latex,
        "cover_latex": cover_res.latex,
        "cv_compiled": cv_res.compiled,
        "cover_compiled": cover_res.compiled,
        "cv_fell_back": cv_res.fell_back,
        "cover_fell_back": cover_res.fell_back,
        "cv_stderr": cv_res.stderr,
        "cover_stderr": cover_res.stderr,
    }

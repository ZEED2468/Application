"""Shared generation engine used by BOTH the autonomous and manual paths.

Produces the identical artifacts: a tailored, truth-bounded CV (with an internal
ATS score) and a 3-paragraph cover letter, both rendered to PDF in R2. VA-confirmed
facts are merged into the profile BEFORE tailoring, so they pass the truth boundary
honestly (they are real, just newly confirmed).
"""

from __future__ import annotations

import structlog

from app.core.enums import CoverLetterStatus, CvStatus, JobStatus, Track
from app.events import names
from app.events.bus import emit as _real_emit
from app.events.contracts import CvGenerated
from app.integrations import r2
from app.llm import cover_letter as cl
from app.llm import hookfinder, tailoring
from app.models.cover_letter import CoverLetter, CoverLetterTemplate
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply import ats, render
from app.repositories import profiles as profiles_repo
from sqlalchemy import select

log = structlog.get_logger(__name__)


def merge_confirmed_facts(profile_dict: dict, confirmed: list[str] | None) -> dict:
    """Add VA-confirmed-true skills into the tailoring input (truth-bounded)."""
    if not confirmed:
        return profile_dict
    merged = dict(profile_dict)
    skills = list(merged.get("skills") or [])
    for fact in confirmed:
        if fact and fact not in skills:
            skills.append(fact)
    merged["skills"] = skills
    return merged


async def generate_cv_and_cover(
    session, *, job: Job, profile: MasterProfile, owner: User,
    role_cv_id=None, confirmed_facts: list[str] | None = None, emit=_real_emit,
) -> tuple[GeneratedCv, CoverLetter]:
    track = job.track or Track.general
    job.status = JobStatus.tailoring

    profile_dict = merge_confirmed_facts(
        profiles_repo.profile_to_dict(profile), confirmed_facts
    )

    # --- Tailored CV (truth-bounded) ---
    cv_json, diff = await tailoring.tailor(
        profile_dict, job_title=job.title, job_description=job.description
    )
    breakdown = ats.score(
        cv_json=cv_json, jd_text=job.description or "", role_title=job.role_title or job.title
    )
    tex = render.build_tex(cv_json, name=owner.name)
    pdf = await render.render_pdf(tex)
    tex_key = f"{job.user_id}/{job.id}/cv.tex"
    pdf_key = f"{job.user_id}/{job.id}/cv.pdf"
    await r2.put_bytes(tex_key, tex.encode(), "application/x-tex")
    cv_pdf_url = await r2.put_bytes(pdf_key, pdf, "application/pdf")

    cv = GeneratedCv(
        user_id=job.user_id, job_id=job.id, master_profile_id=profile.id,
        source_role_cv_id=role_cv_id, cv_json=cv_json, latex_source=tex,
        tex_key=tex_key, pdf_key=pdf_key, pdf_url=cv_pdf_url, tailoring_diff=diff,
        ats_score=breakdown["score"], ats_breakdown=breakdown, status=CvStatus.ready,
    )
    session.add(cv)

    # --- Cover letter (3-paragraph, real hook, same truth boundary) ---
    template = (
        await session.execute(
            select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == job.user_id)
        )
    ).scalar_one_or_none()
    hook = await hookfinder.find_hook(
        company=job.company, track=track, job_description=job.description
    )
    cl_body = await cl.generate_cover_letter(
        candidate_name=owner.name, company=job.company,
        role_title=job.role_title or job.title, track=track, hook=hook,
        profile=profile_dict, jd_text=job.description,
        template_body=template.body if template else None,
    )
    cl_tex = render.build_cover_letter_tex(cl_body, name=owner.name)
    cl_pdf = await render.render_pdf(cl_tex)
    cl_tex_key = f"{job.user_id}/{job.id}/cover.tex"
    cl_pdf_key = f"{job.user_id}/{job.id}/cover.pdf"
    await r2.put_bytes(cl_tex_key, cl_tex.encode(), "application/x-tex")
    cl_pdf_url = await r2.put_bytes(cl_pdf_key, cl_pdf, "application/pdf")

    cover = CoverLetter(
        user_id=job.user_id, job_id=job.id, template_id=template.id if template else None,
        body=cl_body, tex_key=cl_tex_key, pdf_key=cl_pdf_key, pdf_url=cl_pdf_url,
        status=CoverLetterStatus.ready,
    )
    session.add(cover)

    job.status = JobStatus.ready
    await session.flush()
    emit(names.CV_GENERATED, CvGenerated(user_id=job.user_id, job_id=job.id, generated_cv_id=cv.id))
    log.info("generation.done", job_id=str(job.id), ats=breakdown["score"])
    return cv, cover

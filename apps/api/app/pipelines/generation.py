"""Shared generation engine used by BOTH the autonomous and manual paths.

Produces the identical artifacts: a tailored, truth-bounded CV (with an internal
ATS score) and a 3-paragraph cover letter, both rendered to PDF in R2. VA-confirmed
facts are merged into the profile BEFORE tailoring, so they pass the truth boundary
honestly (they are real, just newly confirmed).
"""

from __future__ import annotations

import structlog
from sqlalchemy import select

from app.config import settings
from app.core.enums import CoverLetterStatus, CvStatus, JobStatus, RunState, Track
from app.cv_engine.ingest import build_ledger
from app.cv_engine.runs.machine import run_pipeline
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

log = structlog.get_logger(__name__)


async def _render_checked(tex: str, *, label: str, job_id) -> tuple[bytes, str | None]:
    """Compile via the checked renderer so failures are visible; fall back to the stub
    PDF (so the pipeline still completes) and return the stderr for the record."""
    pdf, stderr = await render.render_pdf_checked(tex)
    if pdf is not None:
        return pdf, None
    log.warning("generation.render_failed", label=label, job_id=str(job_id),
                stderr=(stderr or "")[:500])
    return await render.render_pdf(tex), (stderr or "compile failed")


def enrich_from_verified_extras(cv_json: dict, profile_dict: dict) -> dict:
    """Surface the user's structured verified extras as real CV sections.

    Deterministic and strictly truth-bounded: every item comes straight from the
    profile's `verified_extras` (user-asserted-true facts), so a diligently-filled
    profile yields a richer CV instead of everything collapsing into a flat skills
    blob. Certifications and languages become their own sections; open-source and
    side-project names join Projects. The category set here MUST match the promoted
    set excluded from the flat skills list in `profiles.PROMOTED_EXTRA_CATEGORIES`.
    """
    extras = profile_dict.get("verified_extras") or {}

    def _terms(cat: str) -> list[str]:
        v = extras.get(cat)
        return [str(x).strip() for x in v if str(x).strip()] if isinstance(v, list) else []

    for cat in ("certifications", "languages"):
        terms = _terms(cat)
        if terms:
            cv_json[cat] = list(dict.fromkeys([*(cv_json.get(cat) or []), *terms]))

    extra_projects = _terms("open_source") + _terms("side_projects")
    if extra_projects:
        projects = list(cv_json.get("projects") or [])
        seen = {str((p or {}).get("name", "")).lower() for p in projects if isinstance(p, dict)}
        for name in extra_projects:
            if name.lower() not in seen:
                projects.append({"name": name})
                seen.add(name.lower())
        cv_json["projects"] = projects
    return cv_json


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
    # The candidate's REAL profile view (skills flattened) — used both as the owned-skill set below
    # and as the independent grounding ledger for the engine.
    profile_cv = {**profile_dict,
                  "skills": tailoring._flatten_skills(profile_dict.get("skills"))}
    owned_tokens = ats._cv_tokens(ats._cv_text(profile_cv))
    # JD-critical techs drive an explicit achievement reframe — but ONLY the ones the candidate
    # actually has. Emphasizing an un-owned critical tells the model to feature a skill the profile
    # lacks, which it fabricates (and grounding then blocks). Un-owned criticals are the JD gaps the
    # engine asks about (PR 2), never inventions.
    priority_techs = [
        k for k in ats.critical_keywords(job.description or "")
        if ats._normalize_token(k) in owned_tokens
    ]
    cv_json, diff = await tailoring.tailor(
        profile_dict, job_title=job.title, job_description=job.description,
        priority_techs=priority_techs,
    )
    # Surface the user's structured verified extras (certifications, languages, extra
    # projects) as real CV sections — truth-bounded, straight from the profile.
    cv_json = enrich_from_verified_extras(cv_json, profile_dict)

    # The CV engine FINISHES the CV: it grounds the tailored content against the candidate's REAL
    # profile (an independent ledger), repairs/renders/judges it, and its verified output becomes
    # the GeneratedCv. allow_suspend=False — a genuine gap is flagged (needs_review), never a stop.
    run = await run_pipeline(
        session, user_id=job.user_id, job_id=job.id, allow_suspend=False,
        input={
            "cv_json": cv_json, "ledger": build_ledger({"cv_json": profile_cv}),
            "jd_text": job.description or "", "role_title": job.role_title or job.title,
            "track": track.value, "name": owner.name,
        },
    )
    final_cv_json = run.result_cv_json or cv_json
    breakdown = run.breakdown or ats.score(
        cv_json=final_cv_json, jd_text=job.description or "",
        role_title=job.role_title or job.title, gate={},
    )
    tex = run.tex or render.build_tex(final_cv_json, name=owner.name)
    pdf = (await r2.get_bytes(run.artifact_ref)) if run.artifact_ref else None
    if pdf is None:                       # engine didn't compile (no tectonic / gap) → stub render
        pdf = await render.render_pdf(tex)
    diff["engine"] = {
        "run_id": str(run.id), "state": run.state.value, "score": run.score,
        "violations": len(run.violations or []), "needs_input": run.needs_input,
    }

    # Ready only when the engine RELEASED (gate passed + no blocking violation). Fake/dev mode
    # keeps the stub-render convenience.
    cv_ready = settings.use_fake_integrations or run.state == RunState.released

    tex_key = f"{job.user_id}/{job.id}/cv.tex"
    pdf_key = f"{job.user_id}/{job.id}/cv.pdf"
    await r2.put_bytes(tex_key, tex.encode(), "application/x-tex")
    cv_pdf_url = await r2.put_bytes(pdf_key, pdf, "application/pdf")

    cv = GeneratedCv(
        user_id=job.user_id, job_id=job.id, master_profile_id=profile.id,
        source_role_cv_id=role_cv_id, cv_json=final_cv_json, latex_source=tex,
        tex_key=tex_key, pdf_key=pdf_key, pdf_url=cv_pdf_url, tailoring_diff=diff,
        ats_score=breakdown.get("score"), ats_breakdown=breakdown,
        status=CvStatus.ready if cv_ready else CvStatus.failed,
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
    cl_pdf, _cl_stderr = await _render_checked(cl_tex, label="cover", job_id=job.id)
    cl_tex_key = f"{job.user_id}/{job.id}/cover.tex"
    cl_pdf_key = f"{job.user_id}/{job.id}/cover.pdf"
    await r2.put_bytes(cl_tex_key, cl_tex.encode(), "application/x-tex")
    cl_pdf_url = await r2.put_bytes(cl_pdf_key, cl_pdf, "application/pdf")

    cover = CoverLetter(
        user_id=job.user_id, job_id=job.id, template_id=template.id if template else None,
        body=cl_body, latex_source=cl_tex, tex_key=cl_tex_key, pdf_key=cl_pdf_key,
        pdf_url=cl_pdf_url, status=CoverLetterStatus.ready,
    )
    session.add(cover)

    if cv_ready:
        job.status = JobStatus.ready
    else:
        # Don't advance to ready — the engine didn't RELEASE it. Leave it in-progress so it can't
        # be submitted; the run's state + violations (surfaced via cv_run on the job) say why.
        job.status = JobStatus.tailoring
        log.warning("generation.cv_not_ready", job_id=str(job.id),
                    run_state=run.state.value, needs_input=bool(run.needs_input))
    await session.flush()
    emit(names.CV_GENERATED, CvGenerated(user_id=job.user_id, job_id=job.id, generated_cv_id=cv.id))
    log.info("generation.done", job_id=str(job.id), ats=breakdown.get("score"), cv_ready=cv_ready)
    return cv, cover

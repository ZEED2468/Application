"""Shared generation engine used by BOTH the autonomous and manual paths.

Produces the identical artifacts: a tailored, truth-bounded CV (with an internal
ATS score) and a 3-paragraph cover letter, both rendered to PDF in R2. VA-confirmed
facts are merged into the profile BEFORE tailoring, so they pass the truth boundary
honestly (they are real, just newly confirmed).
"""

from __future__ import annotations

import shutil

import structlog

from app.config import settings
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
from app.pipelines.apply import ats, format_gate, render
from app.repositories import profiles as profiles_repo
from sqlalchemy import select

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


def _facts_present(tex: str, *, name: str, cv_json: dict) -> bool:
    """Sanity check that the rendered LaTeX carries the candidate's real anchors."""
    low = tex.lower()
    anchors = [name]
    exp = cv_json.get("experience") or []
    if exp and isinstance(exp[0], dict) and exp[0].get("company"):
        anchors.append(str(exp[0]["company"]))
    return all(str(a).lower() in low for a in anchors if a)


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
    # JD-critical techs drive an explicit achievement reframe of the candidate's REAL
    # experience (computed from the JD alone, so it's valid pre-tailoring).
    priority_techs = ats.critical_keywords(job.description or "")
    cv_json, diff = await tailoring.tailor(
        profile_dict, job_title=job.title, job_description=job.description,
        priority_techs=priority_techs,
    )
    # Surface the user's structured verified extras (certifications, languages, extra
    # projects) as real CV sections — truth-bounded, straight from the profile.
    cv_json = enrich_from_verified_extras(cv_json, profile_dict)
    tex = render.build_tex(cv_json, name=owner.name)
    pdf, cv_stderr = await _render_checked(tex, label="cv", job_id=job.id)

    # I2 — the format gate over the *real* rendered artifact. When the compile failed the
    # PDF is a stub, so gate the true output (None on failure); when no LaTeX engine is
    # available the gate is `unevaluated`, never a fabricated pass.
    has_compiler = shutil.which("tectonic") is not None
    gate = format_gate.evaluate(
        tex=tex, pdf=(pdf if cv_stderr is None else None), has_compiler=has_compiler
    )
    breakdown = ats.score(
        cv_json=cv_json, jd_text=job.description or "",
        role_title=job.role_title or job.title, gate=gate,
    )
    diff["render"] = {
        "cv_ok": cv_stderr is None, "gate": gate,
        "facts_ok": _facts_present(tex, name=owner.name, cv_json=cv_json),
    }
    if cv_stderr:
        diff["render"]["cv_stderr"] = cv_stderr[:500]

    # A CV may only be presented as ready when it actually rendered AND parses. In fake/dev
    # mode (no real integrations) the stub render is a known dev convenience, so we keep the
    # ready state; in real mode a failed/unevaluated gate is a fix-first state, not "ready".
    cv_ready = settings.use_fake_integrations or gate["status"] == "pass"

    tex_key = f"{job.user_id}/{job.id}/cv.tex"
    pdf_key = f"{job.user_id}/{job.id}/cv.pdf"
    await r2.put_bytes(tex_key, tex.encode(), "application/x-tex")
    cv_pdf_url = await r2.put_bytes(pdf_key, pdf, "application/pdf")

    cv = GeneratedCv(
        user_id=job.user_id, job_id=job.id, master_profile_id=profile.id,
        source_role_cv_id=role_cv_id, cv_json=cv_json, latex_source=tex,
        tex_key=tex_key, pdf_key=pdf_key, pdf_url=cv_pdf_url, tailoring_diff=diff,
        ats_score=breakdown["score"], ats_breakdown=breakdown,
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
        # Don't advance to ready — the CV didn't earn it. Leave it in-progress so it can't
        # be submitted, and log why (surfaced to the user via cv.status + the gate reasons).
        job.status = JobStatus.tailoring
        log.warning("generation.cv_not_ready", job_id=str(job.id),
                    gate=gate["status"], reasons=gate.get("reasons"))
    await session.flush()
    emit(names.CV_GENERATED, CvGenerated(user_id=job.user_id, job_id=job.id, generated_cv_id=cv.id))
    log.info("generation.done", job_id=str(job.id), ats=breakdown["score"], cv_ready=cv_ready)
    return cv, cover

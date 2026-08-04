"""Onboarding API — multi-role CV upload, cover-letter template, profile review.

Upload one CV per role -> R2 -> parse into a master_profile (truth corpus + naive
skills) -> hunter reviews/corrects/confirms.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._files import serve_key
from app.core.enums import LatexKind, ParseStatus, Track
from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import current_user
from app.integrations import r2

_ALLOWED_CV_EXT = {".pdf", ".doc", ".docx"}
_ALLOWED_TEMPLATE_EXT = _ALLOWED_CV_EXT | {".txt"}
_ALLOWED_LATEX_EXT = {".tex", ".txt"}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_upload(filename: str | None, data: bytes, allowed: set[str]) -> str:
    """Return the lowercased extension after checking type + size, else raise 400."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in allowed:
        raise DomainError(
            f"Unsupported file type '{ext or '?'}'. Allowed: {', '.join(sorted(allowed))}."
        )
    if not data:
        raise DomainError("Empty file.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise DomainError("File too large (max 10 MB).")
    return ext


def _serve_extras(ext: str) -> tuple[str, bool]:
    """(content_type, inline) for serving an uploaded source file by extension."""
    if ext == ".pdf":
        return "application/pdf", True
    return "application/octet-stream", False
from app.models.cover_letter import CoverLetterTemplate
from app.models.latex_template import LatexTemplate
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.models.user_llm_credential import UserLlmCredential

import shutil

from app.llm import cv_structure
from app.pipelines.apply import format_gate, render
from app.pipelines.apply.cv_parse import extract_text_from_bytes, naive_skills
from app.pipelines.apply.latex_safety import assert_safe

router = APIRouter(tags=["onboarding"])


def _extract_text(filename: str, data: bytes) -> str:
    return extract_text_from_bytes(filename, data)


def _naive_skills(text: str, *, top: int = 30) -> list[str]:
    return naive_skills(text, top=top)


class RoleCvOut(BaseModel):
    filename: str | None
    parsed: bool


class ProfileOut(BaseModel):
    track: Track
    headline: str | None
    summary: str | None
    skills: list | dict
    target_roles: list[str] = []
    confirmed: bool = False
    role_cv: RoleCvOut | None = None
    latex_cv: bool = False  # a CV LaTeX template is on file for this track
    latex_cover: bool = False  # a cover-letter LaTeX template is on file for this track
    verified_extras: dict = {}
    preferred_skills: list[str] = []
    career_preferences: dict = {}
    links: dict = {}
    preferred_locations: list[str] = []
    preferred_job_types: list[str] = []
    salary_expectation: dict = {}


class VerifiedExtrasBody(BaseModel):
    extras: dict


class CareerDetailsBody(BaseModel):
    links: dict = {}
    preferred_locations: list[str] = []
    preferred_job_types: list[str] = []
    salary_expectation: dict = {}


class PreferencesBody(BaseModel):
    preferred_skills: list[str] = []
    career_preferences: dict = {}


class ActiveTrackBody(BaseModel):
    track: Track | None = None


class LatexTemplateOut(BaseModel):
    track: Track
    kind: LatexKind
    filename: str | None = None
    has_source: bool = False
    source: str | None = None
    # ATS format gate from a trial compile at save (status: pass|fail|unevaluated).
    gate: dict | None = None


async def _template_gate(source: str | None) -> dict | None:
    """Validate + gate a template at save time: reject forbidden LaTeX primitives (400),
    then trial-compile and evaluate the ATS format gate (non-blocking — a template that
    won't compile is stored with gate=fail so the user is told before regeneration)."""
    if not source or not source.strip():
        return None
    assert_safe(source)  # DomainError(400) on shell/IO primitives — never store an unsafe template
    has_compiler = shutil.which("tectonic") is not None
    pdf, _stderr = await render.render_pdf_checked(source)
    return format_gate.evaluate(tex=source, pdf=pdf, has_compiler=has_compiler)


class LatexTemplateBody(BaseModel):
    track: Track
    kind: LatexKind
    source: str


class TargetRolesBody(BaseModel):
    roles: list[str]


class TemplateBody(BaseModel):
    body: str
    name: str | None = None


class CoverLetterTemplateOut(BaseModel):
    body: str | None = None
    filename: str | None = None
    name: str | None = None


async def _get_or_create_template(session: AsyncSession, user_id) -> CoverLetterTemplate:
    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user_id)
    )).scalar_one_or_none()
    if tpl is None:
        tpl = CoverLetterTemplate(user_id=user_id)
        session.add(tpl)
    return tpl


def _template_out(tpl: CoverLetterTemplate) -> CoverLetterTemplateOut:
    return CoverLetterTemplateOut(
        body=tpl.body,
        filename=tpl.original_filename,
        name=tpl.name,
    )


async def _get_or_create_latex(
    session: AsyncSession, user_id, track: Track, kind: LatexKind
) -> LatexTemplate:
    lt = (await session.execute(
        select(LatexTemplate).where(
            LatexTemplate.user_id == user_id,
            LatexTemplate.track == track,
            LatexTemplate.kind == kind,
        )
    )).scalar_one_or_none()
    if lt is None:
        lt = LatexTemplate(user_id=user_id, track=track, kind=kind)
        session.add(lt)
    return lt


def _latex_out(lt: LatexTemplate) -> LatexTemplateOut:
    return LatexTemplateOut(
        track=lt.track, kind=lt.kind, filename=lt.original_filename,
        has_source=bool(lt.source), source=lt.source, gate=lt.gate,
    )


@router.get("/profiles", response_model=list[ProfileOut])
async def list_profiles(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[ProfileOut]:
    profiles = (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalars().all()
    role_cvs = {
        rc.track: rc
        for rc in (await session.execute(
            select(RoleCv).where(RoleCv.user_id == user.id)
        )).scalars().all()
    }
    latex = {
        (lt.track, lt.kind): lt
        for lt in (await session.execute(
            select(LatexTemplate).where(LatexTemplate.user_id == user.id)
        )).scalars().all()
    }
    out: list[ProfileOut] = []
    for p in profiles:
        rc = role_cvs.get(p.track)
        parsed = rc is not None and rc.parse_status is ParseStatus.parsed
        cv_tpl = latex.get((p.track, LatexKind.cv))
        cover_tpl = latex.get((p.track, LatexKind.cover))
        out.append(ProfileOut(
            track=p.track,
            headline=p.headline,
            summary=p.summary,
            skills=p.skills,
            target_roles=list(p.target_roles or []),
            confirmed=bool(p.confirmed),
            role_cv=(
                RoleCvOut(
                    filename=rc.original_filename,
                    parsed=parsed,
                )
                if rc is not None
                else None
            ),
            latex_cv=bool(cv_tpl and cv_tpl.source),
            latex_cover=bool(cover_tpl and cover_tpl.source),
            verified_extras=p.verified_extras or {},
            preferred_skills=list(p.preferred_skills or []),
            career_preferences=p.career_preferences or {},
            links=p.links or {},
            preferred_locations=list(p.preferred_locations or []),
            preferred_job_types=list(p.preferred_job_types or []),
            salary_expectation=p.salary_expectation or {},
        ))
    return out


@router.post("/onboarding/role-cv")
async def upload_role_cv(
    track: Track = Form(...), file: UploadFile = File(...),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    data = await file.read()
    ext = _validate_upload(file.filename, data, _ALLOWED_CV_EXT)
    # Stable key so a re-upload overwrites (no orphaned objects); keep filename for display.
    key = f"{user.id}/role-cv/{track.value}/source{ext}"
    await r2.put_bytes(key, data, file.content_type or "application/octet-stream")

    text = _extract_text(file.filename or "", data)
    skills = _naive_skills(text)

    role_cv = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == track)
    )).scalar_one_or_none()
    if role_cv is None:
        role_cv = RoleCv(user_id=user.id, track=track)
        session.add(role_cv)
    role_cv.original_filename = file.filename
    role_cv.source_file_key = key
    role_cv.parse_status = ParseStatus.parsed if text else ParseStatus.failed

    # Seed/refresh the master profile for this track (truth corpus = the real CV text).
    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == user.id, MasterProfile.track == track
        )
    )).scalar_one_or_none()
    if profile is None:
        profile = MasterProfile(user_id=user.id, track=track, experience=[], projects=[],
                                education=[], links={})
        session.add(profile)
    profile.truth_corpus = text or profile.truth_corpus
    structured = await cv_structure.structure_cv(text, track=track.value)
    cv_structure.apply_to_profile(profile, structured)
    if not profile.skills and skills:
        profile.skills = skills
    profile.confirmed = False
    await session.flush()
    exp_count = len(profile.experience or [])
    return {
        "role_cv_id": str(role_cv.id),
        "parse_status": role_cv.parse_status.value,
        "skills_found": len(profile.skills) if isinstance(profile.skills, list) else len(skills),
        "structured_by": structured.structured_by,
        "experience_entries": exp_count,
    }


@router.get("/onboarding/cover-letter-template", response_model=CoverLetterTemplateOut)
async def get_template(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> CoverLetterTemplateOut:
    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()
    if tpl is None:
        return CoverLetterTemplateOut()
    return _template_out(tpl)


@router.post("/onboarding/cover-letter-template/upload")
async def upload_template_file(
    file: UploadFile = File(...),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> CoverLetterTemplateOut:
    data = await file.read()
    filename = file.filename or "template.txt"
    ext = _validate_upload(filename, data, _ALLOWED_TEMPLATE_EXT)
    key = f"{user.id}/cover-letter-template/source{ext}"
    await r2.put_bytes(key, data, file.content_type or "application/octet-stream")

    text = _extract_text(filename, data).strip()
    tpl = await _get_or_create_template(session, user.id)
    tpl.original_filename = filename
    tpl.source_file_key = key
    if text:
        tpl.body = text
    await session.flush()
    return _template_out(tpl)


@router.put("/onboarding/cover-letter-template", response_model=CoverLetterTemplateOut)
async def set_template(
    body: TemplateBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> CoverLetterTemplateOut:
    tpl = await _get_or_create_template(session, user.id)
    tpl.body = body.body
    tpl.name = body.name
    await session.flush()
    return _template_out(tpl)


@router.put("/profiles/{track}/target-roles")
async def set_target_roles(
    track: Track, body: TargetRolesBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """Set the job titles discovery should scrape for on this track."""
    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == user.id, MasterProfile.track == track
        )
    )).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Upload a source CV for this track first.")
    cleaned = list(dict.fromkeys(r.strip() for r in body.roles if r and r.strip()))[:20]
    profile.target_roles = cleaned
    await session.flush()
    return {"track": track.value, "target_roles": cleaned}


async def _require_profile(session, user_id, track: Track) -> MasterProfile:
    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == user_id, MasterProfile.track == track
        )
    )).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Upload a source CV for this track first.")
    return profile


@router.put("/profiles/{track}/verified-extras")
async def set_verified_extras(
    track: Track, body: VerifiedExtrasBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """Set structured, user-verified knowledge not on the CV (part of the truth corpus)."""
    profile = await _require_profile(session, user.id, track)
    cleaned: dict[str, list[str]] = {}
    for k, v in (body.extras or {}).items():
        if not isinstance(v, list):
            continue
        items = list(dict.fromkeys(str(x).strip() for x in v if str(x).strip()))[:50]
        if items:
            cleaned[str(k)[:60]] = items
    profile.verified_extras = cleaned
    await session.flush()
    return {"track": track.value, "verified_extras": cleaned}


@router.put("/profiles/{track}/preferences")
async def set_preferences(
    track: Track, body: PreferencesBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """Per-track preferred skills to emphasize + freeform career preferences (R3)."""
    profile = await _require_profile(session, user.id, track)
    profile.preferred_skills = list(dict.fromkeys(
        s.strip() for s in body.preferred_skills if s and s.strip()
    ))[:40]
    profile.career_preferences = body.career_preferences or {}
    await session.flush()
    return {
        "track": track.value,
        "preferred_skills": profile.preferred_skills,
        "career_preferences": profile.career_preferences,
    }


@router.put("/profiles/{track}/career-details")
async def set_career_details(
    track: Track, body: CareerDetailsBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """Career Workspace details (R8): links + preferred locations/job-types + salary."""
    profile = await _require_profile(session, user.id, track)
    profile.links = body.links or {}
    profile.preferred_locations = list(dict.fromkeys(
        s.strip() for s in body.preferred_locations if s and s.strip()
    ))[:30]
    profile.preferred_job_types = list(dict.fromkeys(
        s.strip() for s in body.preferred_job_types if s and s.strip()
    ))[:15]
    profile.salary_expectation = body.salary_expectation or {}
    await session.flush()
    return {
        "track": track.value, "links": profile.links,
        "preferred_locations": profile.preferred_locations,
        "preferred_job_types": profile.preferred_job_types,
        "salary_expectation": profile.salary_expectation,
    }


@router.put("/me/active-track")
async def set_active_track(
    body: ActiveTrackBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """Set the hunter's currently-active track (drives the dashboard track switcher)."""
    user.active_track = body.track
    await session.flush()
    return {"active_track": body.track.value if body.track else None}


@router.get("/onboarding/status")
async def onboarding_status(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    """First-run completeness + the next required action (drives guided onboarding, R2)."""
    profiles = (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalars().all()
    role_cvs = {
        rc.track: rc for rc in (await session.execute(
            select(RoleCv).where(RoleCv.user_id == user.id)
        )).scalars().all()
    }
    has_key = (await session.execute(
        select(UserLlmCredential.id).where(UserLlmCredential.user_id == user.id).limit(1)
    )).first() is not None

    tracks = []
    for p in profiles:
        rc = role_cvs.get(p.track)
        tracks.append({
            "track": p.track.value,
            "has_cv": rc is not None,
            "parsed": rc is not None and rc.parse_status is ParseStatus.parsed,
            "confirmed": bool(p.confirmed),
            "has_target_roles": bool(p.target_roles),
        })

    steps = [
        {"key": "upload_cv", "label": "Upload a source CV per track",
         "done": bool(role_cvs), "href": "/profile"},
        {"key": "confirm", "label": "Confirm a profile",
         "done": any(p.confirmed for p in profiles), "href": "/profile"},
        {"key": "target_roles", "label": "Set target roles",
         "done": any(p.target_roles for p in profiles), "href": "/profile"},
        {"key": "api_key", "label": "Add an AI provider key",
         "done": has_key, "href": "/settings"},
    ]
    next_action = next((s for s in steps if not s["done"]), None)
    return {
        "tracks": tracks,
        "steps": steps,
        "next_action": next_action,
        "complete": all(s["done"] for s in steps),
    }


@router.post("/profiles/{track}/confirm")
async def confirm_profile(
    track: Track,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == user.id, MasterProfile.track == track
        )
    )).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("No profile for this track — upload a source CV first.")
    role_cv = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == track)
    )).scalar_one_or_none()
    if role_cv is None or role_cv.parse_status is not ParseStatus.parsed:
        raise NotFoundError("Upload and parse a source CV before confirming.")
    profile.confirmed = True
    await session.flush()
    return {"confirmed": True, "track": track.value}


@router.get("/onboarding/role-cv/{track}/file")
async def download_role_cv(
    track: Track,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    """Re-download the hunter's uploaded source CV for a track (safe recovery)."""
    rc = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == track)
    )).scalar_one_or_none()
    if rc is None or not rc.source_file_key:
        raise NotFoundError("No source CV uploaded for this track.")
    ext = os.path.splitext(rc.source_file_key)[1].lower()
    content_type, inline = _serve_extras(ext)
    return await serve_key(
        rc.source_file_key, filename=rc.original_filename or f"cv-{track.value}{ext}",
        content_type=content_type, inline=inline,
    )


@router.get("/onboarding/cover-letter-template/file")
async def download_template_file(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    """Re-download the hunter's uploaded cover-letter template source file."""
    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()
    if tpl is None or not tpl.source_file_key:
        raise NotFoundError("No template file uploaded.")
    ext = os.path.splitext(tpl.source_file_key)[1].lower()
    content_type, inline = _serve_extras(ext)
    return await serve_key(
        tpl.source_file_key, filename=tpl.original_filename or f"cover-letter-template{ext}",
        content_type=content_type, inline=inline,
    )


# --- Per-track LaTeX templates (the design skeletons used by the regeneration engine) ---


@router.get("/onboarding/latex-templates", response_model=list[LatexTemplateOut])
async def list_latex_templates(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> list[LatexTemplateOut]:
    rows = (await session.execute(
        select(LatexTemplate).where(LatexTemplate.user_id == user.id)
    )).scalars().all()
    return [_latex_out(lt) for lt in rows]


@router.get("/onboarding/latex-template", response_model=LatexTemplateOut)
async def get_latex_template(
    track: Track, kind: LatexKind,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> LatexTemplateOut:
    lt = (await session.execute(
        select(LatexTemplate).where(
            LatexTemplate.user_id == user.id,
            LatexTemplate.track == track,
            LatexTemplate.kind == kind,
        )
    )).scalar_one_or_none()
    if lt is None:
        return LatexTemplateOut(track=track, kind=kind)
    return _latex_out(lt)


@router.post("/onboarding/latex-template/upload", response_model=LatexTemplateOut)
async def upload_latex_template(
    track: Track = Form(...), kind: LatexKind = Form(...), file: UploadFile = File(...),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> LatexTemplateOut:
    data = await file.read()
    filename = file.filename or f"{kind.value}.tex"
    _validate_upload(filename, data, _ALLOWED_LATEX_EXT)
    ext = os.path.splitext(filename)[1].lower()
    # Stable key so a re-upload overwrites (no orphaned objects).
    key = f"{user.id}/latex-template/{track.value}/{kind.value}/source{ext}"
    await r2.put_bytes(key, data, "application/x-tex")
    lt = await _get_or_create_latex(session, user.id, track, kind)
    lt.original_filename = filename
    lt.source_file_key = key
    # LaTeX is plain text — keep the exact source (don't run it through a doc parser).
    lt.source = data.decode("utf-8", "replace")
    lt.gate = await _template_gate(lt.source)  # reject unsafe; cache the format gate
    await session.flush()
    return _latex_out(lt)


@router.put("/onboarding/latex-template", response_model=LatexTemplateOut)
async def set_latex_template(
    body: LatexTemplateBody,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> LatexTemplateOut:
    """Editor save path — store the LaTeX source typed/edited in the builder."""
    lt = await _get_or_create_latex(session, user.id, body.track, body.kind)
    lt.source = body.source
    lt.gate = await _template_gate(lt.source)  # reject unsafe; cache the format gate
    await session.flush()
    return _latex_out(lt)


@router.get("/onboarding/latex-template/{track}/{kind}/file")
async def download_latex_template(
    track: Track, kind: LatexKind,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
):
    """Re-download the hunter's uploaded LaTeX template source file."""
    lt = (await session.execute(
        select(LatexTemplate).where(
            LatexTemplate.user_id == user.id,
            LatexTemplate.track == track,
            LatexTemplate.kind == kind,
        )
    )).scalar_one_or_none()
    if lt is None or not lt.source_file_key:
        raise NotFoundError("No LaTeX template uploaded for this track/kind.")
    return await serve_key(
        lt.source_file_key, filename=lt.original_filename or f"{kind.value}.tex",
        content_type="application/x-tex", inline=False,
    )

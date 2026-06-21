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
from app.core.enums import ParseStatus, Track
from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import current_user
from app.integrations import r2

_ALLOWED_CV_EXT = {".pdf", ".doc", ".docx"}
_ALLOWED_TEMPLATE_EXT = _ALLOWED_CV_EXT | {".txt"}
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
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User

from app.llm import cv_structure
from app.pipelines.apply.cv_parse import extract_text_from_bytes, naive_skills

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
    confirmed: bool = False
    role_cv: RoleCvOut | None = None


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
    out: list[ProfileOut] = []
    for p in profiles:
        rc = role_cvs.get(p.track)
        parsed = rc is not None and rc.parse_status is ParseStatus.parsed
        out.append(ProfileOut(
            track=p.track,
            headline=p.headline,
            summary=p.summary,
            skills=p.skills,
            confirmed=bool(p.confirmed),
            role_cv=(
                RoleCvOut(
                    filename=rc.original_filename,
                    parsed=parsed,
                )
                if rc is not None
                else None
            ),
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

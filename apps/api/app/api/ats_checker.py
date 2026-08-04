"""Global ATS checker — profile CVs, one-off upload, or pasted text vs a JD."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ParseStatus, Track
from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import bind_user_llm, current_user
from app.llm import ats_analyze, resume_intel, track_classify
from app.models.cover_letter import CoverLetterTemplate
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.pipelines.apply import ats, intel, verbs
from app.pipelines.apply.cv_parse import cv_json_from_text, extract_text_from_bytes
from app.pipelines.apply.profile_cv import cv_text_from_profile
from app.repositories import ats_analysis as ats_repo
from app.repositories import profiles as profiles_repo
from app.repositories import track_match as track_match_repo

router = APIRouter(prefix="/ats", tags=["ats"], dependencies=[Depends(bind_user_llm)])


def _default_role_title(jd_text: str) -> str:
    for line in (jd_text or "").splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return "Role"


def _cover_letter_out(tpl: CoverLetterTemplate | None) -> dict | None:
    if tpl is None or not (tpl.body or tpl.original_filename):
        return None
    return {
        "body": tpl.body,
        "filename": tpl.original_filename,
        "name": tpl.name,
    }


async def _profile_sources(session: AsyncSession, *, user_id) -> list[dict]:
    role_cvs = {
        rc.track: rc
        for rc in (await session.execute(
            select(RoleCv).where(RoleCv.user_id == user_id)
        )).scalars().all()
    }
    profiles = {
        p.track: p
        for p in (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user_id)
        )).scalars().all()
    }
    out: list[dict] = []
    for track in Track:
        rc = role_cvs.get(track)
        profile = profiles.get(track)
        if rc is None or rc.parse_status is not ParseStatus.parsed:
            continue
        text = cv_text_from_profile(profile) if profile else ""
        if not text:
            continue
        out.append({
            "track": track.value,
            "filename": rc.original_filename,
            "word_count": len(re.findall(r"\w+", text)),
            "confirmed": bool(profile.confirmed) if profile else False,
        })
    return out


class SuggestTrackRequest(BaseModel):
    jd_text: str
    role_title: str | None = None


class AtsCheckJsonRequest(BaseModel):
    jd_text: str
    cv_text: str | None = None
    track: Track | None = None
    role_title: str | None = None
    use_ai: bool = True
    # When launched from a job, persist the analysis against it (else standalone).
    job_id: UUID | None = None


async def _resolve_job_id(session, user_id, job_id) -> UUID | None:
    """Validate an optional job binding for a check (owned by the caller), else None."""
    if job_id is None:
        return None
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise NotFoundError("Job not found")
    return job_id


@router.get("/sources")
async def ats_sources(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Uploaded profile CVs + cover letter template for the ATS checker UI."""
    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()
    tracks = await _profile_sources(session, user_id=user.id)
    return {
        "tracks": tracks,
        "cover_letter_template": _cover_letter_out(tpl),
    }


@router.post("/suggest-track")
async def suggest_track(
    body: SuggestTrackRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    jd = body.jd_text.strip()
    if len(jd) < 20:
        raise DomainError("Job description is too short.")
    title = (body.role_title or "").strip() or _default_role_title(jd)
    available = await track_match_repo.available_track_previews(session, user_id=user.id)
    match = await track_classify.classify_best(
        title=title, description=jd, available=available,
    )
    return {
        "track": match.track.value,
        "method": match.method,
        "reason": match.reason,
    }


@router.post("/check")
async def check_ats_multipart(
    jd_text: str = Form(...),
    role_title: str | None = Form(default=None),
    track: str | None = Form(default=None),
    cv_text: str | None = Form(default=None),
    use_ai: bool = Form(default=True),
    job_id: UUID | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Compare a profile CV, upload, or pasted text against a JD."""
    parsed_track = Track(track) if track else None
    bound_job_id = await _resolve_job_id(session, user.id, job_id)
    filename: str | None = None
    text = (cv_text or "").strip()
    cv_source = "paste"

    if file is not None and file.filename:
        data = await file.read()
        filename = file.filename
        extracted = extract_text_from_bytes(file.filename, data).strip()
        if extracted:
            text = extracted
        cv_source = "upload"
    elif len(text) >= 20:
        cv_source = "paste"
    elif parsed_track is not None:
        text, filename, cv_source = await _load_profile_cv(
            session, user_id=user.id, track=parsed_track,
        )

    jd = jd_text.strip()
    if len(jd) < 20:
        raise DomainError("Job description is too short.")

    title = (role_title or "").strip() or _default_role_title(jd)
    track_match = None

    if len(text) < 20:
        available = await track_match_repo.available_track_previews(
            session, user_id=user.id,
        )
        if not available:
            raise DomainError(
                "Provide a CV (paste or upload), or upload profile CVs on the Profile page."
            )
        track_match = await track_classify.classify_best(
            title=title, description=jd, available=available,
        )
        parsed_track = track_match.track
        text, filename, cv_source = await _load_profile_cv(
            session, user_id=user.id, track=parsed_track,
        )
    elif parsed_track is None and cv_source in ("paste", "upload"):
        available = await track_match_repo.available_track_previews(
            session, user_id=user.id,
        )
        if available:
            track_match = await track_classify.classify_best(
                title=title, description=jd, available=available,
            )

    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()

    result = await _run_check(
        jd_text=jd,
        cv_text=text,
        role_title=title,
        use_ai=use_ai,
        cv_filename=filename,
        track=parsed_track,
        cv_source=cv_source,
        track_match=track_match,
        cover_letter_template=_cover_letter_out(tpl),
        verified_terms=await _verified_terms(session, user.id, parsed_track),
        session=session,
        user_id=user.id,
        job_id=bound_job_id,
    )
    return result


@router.post("/check/json")
async def check_ats_json(
    body: AtsCheckJsonRequest,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    jd = body.jd_text.strip()
    if len(jd) < 20:
        raise DomainError("Job description is too short.")

    text = (body.cv_text or "").strip()
    filename: str | None = None
    cv_source = "paste"
    track = body.track

    if track is not None and len(text) < 20:
        text, filename, cv_source = await _load_profile_cv(
            session, user_id=user.id, track=track,
        )
    if len(text) < 20:
        raise DomainError("CV text is too short.")

    title = (body.role_title or "").strip() or _default_role_title(jd)
    bound_job_id = await _resolve_job_id(session, user.id, body.job_id)
    tpl = (await session.execute(
        select(CoverLetterTemplate).where(CoverLetterTemplate.user_id == user.id)
    )).scalar_one_or_none()

    return await _run_check(
        jd_text=jd,
        cv_text=text,
        role_title=title,
        use_ai=body.use_ai,
        cv_filename=filename,
        track=track,
        cv_source=cv_source,
        cover_letter_template=_cover_letter_out(tpl),
        verified_terms=await _verified_terms(session, user.id, track),
        session=session,
        user_id=user.id,
        job_id=bound_job_id,
    )


@router.get("/analysis")
async def latest_analysis(
    job_id: UUID | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict | None:
    """Latest persisted ATS analysis for a job (or the standalone check) — powers the
    LaTeX builder's recommendations from the DB instead of a browser handoff."""
    row = await ats_repo.latest(session, user_id=user.id, job_id=job_id)
    if row is None:
        return None
    b = row.breakdown or {}
    ai = row.ai or {}
    return {
        "analysis_id": str(row.id),
        "version": row.version,
        "gate_status": row.gate_status,
        "score": row.score,
        "recs": {
            "missing_critical": b.get("missing_critical") or [],
            "gaps": ats.gap_skills(b),
            "recommendations": ai.get("recommendations") or [],
        },
    }


async def _load_profile_cv(
    session: AsyncSession, *, user_id, track: Track,
) -> tuple[str, str | None, str]:
    profile = await profiles_repo.get_by_user_track(
        session, user_id=user_id, track=track,
    )
    rc = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user_id, RoleCv.track == track)
    )).scalar_one_or_none()
    if profile is None or rc is None or rc.parse_status is not ParseStatus.parsed:
        raise DomainError(
            f"No parsed {track.value} CV on your profile — upload one on Profile or paste a CV here."
        )
    text = cv_text_from_profile(profile)
    if len(text) < 20:
        raise DomainError(
            f"The {track.value} CV could not be read — re-upload on Profile or paste text here."
        )
    return text, rc.original_filename, "profile"


async def _verified_terms(session: AsyncSession, user_id, track: Track | None) -> list[str]:
    """Flatten a track profile's verified extras + preferred skills (empty if none)."""
    if track is None:
        return []
    profile = await profiles_repo.get_by_user_track(session, user_id=user_id, track=track)
    return profiles_repo._extra_terms(profile) if profile else []


async def _run_check(
    *,
    jd_text: str,
    cv_text: str,
    role_title: str,
    use_ai: bool,
    cv_filename: str | None,
    track: Track | None = None,
    cv_source: str = "paste",
    track_match=None,
    cover_letter_template: dict | None = None,
    verified_terms: list[str] | None = None,
    session: AsyncSession | None = None,
    user_id=None,
    job_id: UUID | None = None,
) -> dict:
    from app.llm import client

    cv_json = cv_json_from_text(cv_text)
    ai_live = client.is_live("ats_analyze")

    # Initial rule pass (feeds the AI prompt).
    breakdown = ats.score(cv_json=cv_json, jd_text=jd_text, role_title=role_title)
    rule_score = breakdown["score"]

    ai_block: dict | None = None
    false_positives: list[str] = []
    if use_ai:
        analysis = await ats_analyze.analyze(
            cv_text=cv_text,
            jd_text=jd_text,
            role_title=role_title,
            rule_score=rule_score,
            breakdown=breakdown,
        )
        ai_block = ats_analyze.analysis_to_dict(analysis)
        ai_block["ai_powered"] = ai_live
        false_positives = analysis.false_positives

    # Apply the AI's false-positive retractions and recompute the single number so the
    # score, gaps and intelligence all reflect the corrected keyword set (one number out).
    if false_positives:
        breakdown = ats.score(
            cv_json=cv_json, jd_text=jd_text, role_title=role_title,
            false_positives=false_positives,
        )
        rule_score = breakdown["score"]
    if track_match is not None:
        breakdown["track_match"] = {
            "track": track_match.track.value,
            "method": track_match.method,
            "reason": track_match.reason,
        }

    # --- Resume Intelligence (deterministic always; advisory when AI is on) ---
    structure = intel.structure_review(cv_text=cv_text, cv_json=cv_json)
    weak_verbs = verbs.detect(intel.bullets_of(cv_json))
    intelligence = {
        "tools": intel.tool_analysis(jd_text=jd_text, cv_json=cv_json, verified_terms=verified_terms),
        "structure": structure,
        "verbs": weak_verbs,
        "lint": intel.ats_lint(
            cv_json=cv_json, breakdown=breakdown, structure=structure, weak_verbs=weak_verbs
        ),
        "advisory": None,
    }
    if use_ai:
        ri = await resume_intel.analyze(
            cv_json=cv_json, cv_text=cv_text, jd_text=jd_text, role_title=role_title,
            breakdown=breakdown, structure=structure, verified_terms=verified_terms,
        )
        intelligence["advisory"] = resume_intel.analysis_to_dict(ri)

    # Persist the result (durable, versioned) so the builder/regen reads it from the DB
    # instead of a browser sessionStorage handoff. Standalone checks persist with job_id=None.
    analysis_id: str | None = None
    version: int | None = None
    if session is not None and user_id is not None:
        row = await ats_repo.record(
            session, user_id=user_id, job_id=job_id,
            track=track.value if track else None, role_title=role_title,
            gate_status=(breakdown.get("gate") or {}).get("status", "unevaluated"),
            score=rule_score, breakdown=breakdown, ai=ai_block, ai_live=ai_live,
        )
        analysis_id, version = str(row.id), row.version

    return {
        "role_title": role_title,
        "track": track.value if track else None,
        "cv_source": cv_source,
        "cv_filename": cv_filename,
        "cv_word_count": len(re.findall(r"\w+", cv_text)),
        "track_match": breakdown.get("track_match"),
        "cover_letter_template": cover_letter_template,
        "ai_live": ai_live,
        "analysis_id": analysis_id,
        "version": version,
        "rule_based": {
            "score": rule_score,
            "breakdown": breakdown,
            "gaps": ats.gap_skills(breakdown),
        },
        "ai": ai_block,
        "intelligence": intelligence,
    }

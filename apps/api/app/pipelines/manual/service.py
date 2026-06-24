"""Manual (VA chatbot) application path.

Paste JD -> extract role + classify track -> select role_cv -> ATS comparison ->
raise confirm-true prompts -> generate CV + cover letter -> create the SAME
job/generated_cv/cover_letter/application objects as the autonomous path, so the
tracker stays in sync. The truth boundary holds: only VA-confirmed-true facts feed
tailoring.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select

from app.core.enums import (
    ApplicationStatus,
    ChatPromptKind,
    ChatState,
    JobSourceName,
    JobStatus,
    Origin,
    Track,
)
from app.events import names
from app.events.bus import emit as _real_emit
from app.events.contracts import (
    ApplicationSubmitted,
    ChatApplicationCreated,
    ChatCvMatched,
    ChatPromptsRaised,
    ChatSessionStarted,
)
from app.llm import track_classify
from app.llm import tailoring
from app.llm import ats_vet
from app.models.application import Application
from app.models.chat import ChatPrompt, ChatSession
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.pipelines.apply import ats
from app.pipelines import generation
from app.repositories import applications as app_repo
from app.repositories import profiles as profiles_repo
from app.repositories import track_match as track_match_repo

log = structlog.get_logger(__name__)


def extract_role_title(jd_text: str) -> str:
    for line in (jd_text or "").splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return "Software Engineer"


def extract_company(jd_text: str) -> str:
    # Stop at sentence/clause punctuation so "at Streamline. We need..." -> "Streamline".
    m = re.search(r"\bat\s+([A-Z][A-Za-z0-9&\- ]{1,40})", jd_text or "")
    if not m:
        return "Company (manual)"
    return " ".join(m.group(1).split()[:4]).strip()


async def _analyze(
    session, *, chat: ChatSession, track_match=None, emit=_real_emit,
) -> list[ChatPrompt]:
    """(Re)compute the role-CV match, ATS preview, and confirm-true prompts for the
    session's current track. Reused by start_session and the track-override path."""
    user_id = chat.user_id
    track = chat.track or Track.general
    role_cv = (
        await session.execute(
            select(RoleCv).where(RoleCv.user_id == user_id, RoleCv.track == track)
        )
    ).scalar_one_or_none()
    profile = await profiles_repo.get_by_user_track(session, user_id=user_id, track=track)
    chat.role_cv_id = role_cv.id if role_cv else None
    chat.state = ChatState.cv_matched
    if role_cv is not None:
        emit(names.CHAT_CV_MATCHED,
             ChatCvMatched(user_id=user_id, chat_session_id=chat.id,
                           role_cv_id=role_cv.id, track=track))

    role_title = chat.role_title or "Role"
    jd_text = chat.jd_text or ""
    profile_dict = profiles_repo.profile_to_dict(profile) if profile else {"skills": []}
    cv_json, _ = await tailoring.tailor(
        profile_dict, job_title=role_title, job_description=jd_text
    )
    breakdown = ats.score(cv_json=cv_json, jd_text=jd_text, role_title=role_title)
    if track_match is not None:
        breakdown["track_match"] = {
            "track": track_match.track.value,
            "method": track_match.method,
            "reason": track_match.reason,
        }
    chat.ats_score = breakdown["score"]
    chat.ats_breakdown = breakdown

    prompts: list[ChatPrompt] = []
    for skill in ats.gap_skills(breakdown):
        p = ChatPrompt(
            user_id=user_id, chat_session_id=chat.id,
            kind=ChatPromptKind.missing_skill_confirm,
            question=(f"The JD calls for \"{skill}\" but it is not reflected in the profile. "
                      f"Does the hunter have genuine {skill} experience?"),
            options=["Yes — add it (true)", "No — leave it out"],
        )
        session.add(p)
        prompts.append(p)
    await session.flush()
    chat.state = ChatState.prompts_raised if prompts else ChatState.ready
    emit(names.CHAT_PROMPTS_RAISED,
         ChatPromptsRaised(user_id=user_id, chat_session_id=chat.id, prompt_count=len(prompts)))
    return prompts


async def start_session(
    session, *, user_id: UUID, jd_text: str, va_id: UUID | None = None,
    surface: str = "dashboard", emit=_real_emit,
) -> tuple[ChatSession, list[ChatPrompt]]:
    """Create a chat session: match a CV, run ATS, and raise gap prompts."""
    role_title = extract_role_title(jd_text)
    available = await track_match_repo.available_track_previews(session, user_id=user_id)
    match = await track_classify.classify_best(
        title=role_title, description=jd_text, available=available,
    )
    track = match.track

    chat = ChatSession(
        user_id=user_id, va_id=va_id, surface=surface, jd_text=jd_text,
        role_title=role_title, track=track, company=extract_company(jd_text),
        state=ChatState.started, confirmed_facts=[],
    )
    session.add(chat)
    await session.flush()
    emit(names.CHAT_SESSION_STARTED, ChatSessionStarted(user_id=user_id, chat_session_id=chat.id))

    prompts = await _analyze(session, chat=chat, track_match=match, emit=emit)
    log.info(
        "manual.session", chat=str(chat.id), track=track.value,
        track_method=match.method, prompts=len(prompts),
    )
    return chat, prompts


async def reanalyze(session, *, chat: ChatSession, emit=_real_emit) -> list[ChatPrompt]:
    """Track changed: drop old prompts and re-run the analysis for the new track."""
    old = (
        await session.execute(
            select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
        )
    ).scalars().all()
    for p in old:
        await session.delete(p)
    await session.flush()
    return await _analyze(session, chat=chat, emit=emit)


async def vet_gaps_with_ai(
    session, *, chat: ChatSession, emit=_real_emit,
) -> list[ChatPrompt]:
    """Re-review rule-based gap prompts with AI (or offline vet in fake mode)."""
    user_id = chat.user_id
    track = chat.track or Track.general
    profile = await profiles_repo.get_by_user_track(session, user_id=user_id, track=track)
    profile_dict = profiles_repo.profile_to_dict(profile) if profile else {"skills": []}
    breakdown = dict(chat.ats_breakdown or {})
    candidate_gaps = ats.gap_skills(breakdown, limit=10)
    missing = breakdown.get("missing_keywords") or []
    matched = breakdown.get("matched_keywords") or []

    result = await ats_vet.vet_gaps(
        profile=profile_dict,
        jd_text=chat.jd_text or "",
        role_title=chat.role_title or "Role",
        candidate_gaps=candidate_gaps,
        missing_keywords=missing,
        matched_keywords=matched,
    )

    existing = (
        await session.execute(
            select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
        )
    ).scalars().all()
    kept: list[ChatPrompt] = []
    for p in existing:
        if p.resolved or p.kind is not ChatPromptKind.missing_skill_confirm:
            kept.append(p)
            continue
        await session.delete(p)

    new_prompts: list[ChatPrompt] = []
    for gap in result.gaps:
        p = ChatPrompt(
            user_id=user_id,
            chat_session_id=chat.id,
            kind=ChatPromptKind.missing_skill_confirm,
            question=gap.question,
            options=["Yes — add it (true)", "No — leave it out"],
        )
        session.add(p)
        new_prompts.append(p)

    breakdown["ai_vetted"] = True
    breakdown["ai_removed"] = result.removed
    if result.notes:
        breakdown["ai_notes"] = result.notes
    chat.ats_breakdown = breakdown

    all_prompts = kept + new_prompts
    await session.flush()
    chat.state = (
        ChatState.prompts_raised if all_prompts else ChatState.ready
    )
    emit(
        names.CHAT_PROMPTS_RAISED,
        ChatPromptsRaised(
            user_id=user_id, chat_session_id=chat.id, prompt_count=len(all_prompts)
        ),
    )
    log.info(
        "manual.ai_vet",
        chat=str(chat.id),
        kept=len(kept),
        new=len(new_prompts),
        removed=len(result.removed),
    )
    return all_prompts


async def add_confirmed_fact(session, *, chat: ChatSession, skill: str) -> ChatSession:
    """Append a VA-asserted-true skill (truth-bounded) the JD didn't surface."""
    skill = (skill or "").strip()
    if skill and skill not in (chat.confirmed_facts or []):
        chat.confirmed_facts = [*(chat.confirmed_facts or []), skill]
    await session.flush()
    return chat


async def answer_prompt(
    session, *, user_id: UUID, prompt_id: UUID, selected: list[str], detail: str | None = None
) -> ChatPrompt:
    """Record a VA's answer. A 'Yes' on a missing-skill prompt confirms it TRUE."""
    prompt = await session.get(ChatPrompt, prompt_id)
    if prompt is None or prompt.user_id != user_id:
        raise ValueError("prompt not found")
    prompt.selected = selected
    prompt.detail = detail
    prompt.resolved = True

    confirmed_true = any("yes" in (s or "").lower() or "true" in (s or "").lower() for s in selected)
    if prompt.kind is ChatPromptKind.missing_skill_confirm and confirmed_true:
        chat = await session.get(ChatSession, prompt.chat_session_id)
        # Extract the skill name from the question (quoted token).
        m = re.search(r'"([^"]+)"', prompt.question)
        skill = m.group(1) if m else (detail or "")
        fact = detail or skill
        if fact and fact not in (chat.confirmed_facts or []):
            chat.confirmed_facts = [*(chat.confirmed_facts or []), fact]
    await session.flush()
    return prompt


async def generate_application(
    session, *, user_id: UUID, chat_session_id: UUID, emit=_real_emit
) -> Job:
    """Generate the tailored CV + cover letter and leave the job `ready`.

    The VA makes the final call and applies on the job detail page (POST /jobs/{id}/apply)
    — generation no longer auto-submits, so manual + automatic converge on the same
    review→apply step.
    """
    chat = await session.get(ChatSession, chat_session_id)
    if chat is None or chat.user_id != user_id:
        raise ValueError("chat session not found")
    track = chat.track or Track.general
    owner = await session.get(User, user_id)
    profile = await profiles_repo.get_by_user_track(session, user_id=user_id, track=track)
    if profile is None:
        profile = MasterProfile(user_id=user_id, track=track, skills=[], experience=[],
                                projects=[], education=[], links={})
        session.add(profile)
        await session.flush()

    company = chat.company or extract_company(chat.jd_text or "")
    dedupe = hashlib.sha256((chat.jd_text or str(chat.id)).encode()).hexdigest()[:32]
    job = Job(
        user_id=user_id, source=JobSourceName.manual, origin=Origin.manual,
        dedupe_key=dedupe, company=company, title=chat.role_title or "Role",
        role_title=chat.role_title, description=chat.jd_text, track=track,
        status=JobStatus.scored,
    )
    session.add(job)
    await session.flush()
    chat.job_id = job.id

    # Shared engine sets job.status = ready when done (same as the autonomous path).
    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=owner,
        role_cv_id=chat.role_cv_id, confirmed_facts=chat.confirmed_facts, emit=emit,
    )
    chat.state = ChatState.application_created  # chat output produced; VA applies next
    await session.flush()
    log.info("manual.generated", job_id=str(job.id), ats=cv.ats_score)
    return job

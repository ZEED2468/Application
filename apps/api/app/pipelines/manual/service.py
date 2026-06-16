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


async def start_session(
    session, *, user_id: UUID, jd_text: str, va_id: UUID | None = None,
    surface: str = "dashboard", emit=_real_emit,
) -> tuple[ChatSession, list[ChatPrompt]]:
    """Create a chat session: match a CV, run ATS, and raise gap prompts."""
    role_title = extract_role_title(jd_text)
    track = track_classify.classify(title=role_title, description=jd_text)

    chat = ChatSession(
        user_id=user_id, va_id=va_id, surface=surface, jd_text=jd_text,
        role_title=role_title, track=track, state=ChatState.started, confirmed_facts=[],
    )
    session.add(chat)
    await session.flush()
    emit(names.CHAT_SESSION_STARTED, ChatSessionStarted(user_id=user_id, chat_session_id=chat.id))

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

    # ATS preview against the (tailored) profile.
    profile_dict = profiles_repo.profile_to_dict(profile) if profile else {"skills": []}
    cv_json, _ = await tailoring.tailor(
        profile_dict, job_title=role_title, job_description=jd_text
    )
    breakdown = ats.score(cv_json=cv_json, jd_text=jd_text, role_title=role_title)
    chat.ats_score = breakdown["score"]
    chat.ats_breakdown = breakdown

    # Raise confirm-true prompts for the top missing skills.
    prompts: list[ChatPrompt] = []
    for skill in ats.gap_skills(breakdown):
        p = ChatPrompt(
            user_id=user_id, chat_session_id=chat.id,
            kind=ChatPromptKind.missing_skill_confirm,
            question=(f"The JD emphasizes \"{skill}\" but it isn't in the profile. "
                      f"Does the hunter genuinely have {skill} experience?"),
            options=["Yes — add it (true)", "No — leave it out"],
        )
        session.add(p)
        prompts.append(p)
    await session.flush()
    chat.state = ChatState.prompts_raised if prompts else ChatState.ready
    emit(names.CHAT_PROMPTS_RAISED,
         ChatPromptsRaised(user_id=user_id, chat_session_id=chat.id, prompt_count=len(prompts)))
    log.info("manual.session", chat=str(chat.id), track=track.value, prompts=len(prompts))
    return chat, prompts


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
) -> Application:
    """Generate CV+cover letter and create the identical application objects."""
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

    company = extract_company(chat.jd_text or "")
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

    cv, _cover = await generation.generate_cv_and_cover(
        session, job=job, profile=profile, owner=owner,
        role_cv_id=chat.role_cv_id, confirmed_facts=chat.confirmed_facts, emit=emit,
    )

    application = Application(
        user_id=user_id, job_id=job.id, generated_cv_id=cv.id, va_id=chat.va_id,
        status=ApplicationStatus.submitted, submitted_at=datetime.now(timezone.utc),
    )
    session.add(application)
    job.status = JobStatus.submitted
    chat.state = ChatState.application_created
    await session.flush()

    app_repo.record_event(
        session, application=application, kind="created",
        actor=f"va:{chat.va_id}" if chat.va_id else "system",
        detail={"origin": "manual", "chat_session": str(chat.id), "ats": cv.ats_score},
    )
    # Identical seam into Pipeline B as the autonomous path.
    emit(names.APPLICATION_SUBMITTED,
         ApplicationSubmitted(user_id=user_id, application_id=application.id,
                              job_id=job.id, track=track))
    emit(names.CHAT_APPLICATION_CREATED,
         ChatApplicationCreated(user_id=user_id, chat_session_id=chat.id,
                                application_id=application.id, job_id=job.id))
    log.info("manual.application_created", application=str(application.id), ats=cv.ats_score)
    return application

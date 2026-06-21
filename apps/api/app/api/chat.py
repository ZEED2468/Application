"""Manual application chatbot API (dashboard-rich; WhatsApp-lite shares the engine)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PrincipalType, Track
from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import Principal, authorize_owner, current_principal, scoped_user_ids
from app.models.chat import ChatPrompt, ChatSession
from app.models.role_cv import RoleCv
from app.pipelines.manual import service

router = APIRouter(prefix="/chat", tags=["chat"])

# Backend prompt kinds -> the frontend PromptKind union (prompt-card.tsx).
_KIND_UI = {
    "missing_skill_confirm": "skill",
    "reframe_confirm": "reframe",
    "seniority_confirm": "detail",
}


class StartRequest(BaseModel):
    jd_text: str
    # Target hunter to apply on behalf of. Optional for a hunter (themselves);
    # a VA assisting >1 hunter must set it. va_id is ignored from the client and
    # taken from the authenticated principal instead.
    user_id: UUID | None = None
    surface: str = "dashboard"


async def _resolve_owner(
    session: AsyncSession, principal: Principal, requested_user_id: UUID | None
) -> tuple[UUID, UUID | None]:
    """Return (owner_user_id, va_id) for a chat action. A hunter acts as itself;
    a VA acts on an assigned hunter (explicit, or the sole one)."""
    if principal.type is PrincipalType.user:
        return principal.id, None
    user_ids = await scoped_user_ids(session, principal)
    if requested_user_id is not None:
        await authorize_owner(session, principal, requested_user_id)
        return requested_user_id, principal.id
    if len(user_ids) == 1:
        return user_ids[0], principal.id
    raise DomainError("Specify user_id: this VA assists multiple hunters.")


class AnswerRequest(BaseModel):
    prompt_id: UUID
    selected: list[str]
    detail: str | None = None


def _prompt_dto(p: ChatPrompt) -> dict:
    # options are stored as plain strings; the UI wants {id, label} (and these are
    # single-select yes/no confirmations, so multi=False).
    options = [{"id": o, "label": o} for o in (p.options or [])]
    return {"id": str(p.id), "question": p.question, "options": options,
            "kind": _KIND_UI.get(p.kind.value, "skill"), "multi": False,
            "selected": p.selected, "resolved": p.resolved}


async def _session_dto(session, chat: ChatSession, prompts: list[ChatPrompt]) -> dict:
    matched_cv = None
    if chat.role_cv_id is not None:
        rc = await session.get(RoleCv, chat.role_cv_id)
        if rc is not None:
            matched_cv = {"track": rc.track.value, "filename": rc.original_filename}
    return {
        "session_id": str(chat.id), "state": chat.state.value,
        "track": chat.track.value if chat.track else None,
        "track_match": (chat.ats_breakdown or {}).get("track_match"),
        "company": chat.company, "role_title": chat.role_title,
        "matched_cv": matched_cv,
        "ats": {"score": chat.ats_score, "breakdown": chat.ats_breakdown},
        "confirmed_facts": list(chat.confirmed_facts or []),
        "job_id": str(chat.job_id) if chat.job_id else None,
        "prompts": [_prompt_dto(p) for p in prompts],
    }


async def _session_dto_for(session, chat: ChatSession) -> dict:
    prompts = list((await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
    )).scalars().all())
    return await _session_dto(session, chat, prompts)


async def _owned_chat(session, principal: Principal, session_id: UUID) -> ChatSession:
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise NotFoundError("Chat session not found")
    await authorize_owner(session, principal, chat.user_id)
    return chat


class UpdateRequest(BaseModel):
    company: str | None = None
    role_title: str | None = None
    track: Track | None = None


class FactRequest(BaseModel):
    skill: str


@router.post("/sessions")
async def start(
    body: StartRequest,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    owner_id, va_id = await _resolve_owner(session, principal, body.user_id)
    chat, prompts = await service.start_session(
        session, user_id=owner_id, jd_text=body.jd_text, va_id=va_id, surface=body.surface
    )
    return await _session_dto(session, chat, prompts)


@router.post("/sessions/{session_id}/answer")
async def answer(
    session_id: UUID, body: AnswerRequest,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    chat = await _owned_chat(session, principal, session_id)
    await service.answer_prompt(
        session, user_id=chat.user_id, prompt_id=body.prompt_id,
        selected=body.selected, detail=body.detail,
    )
    return await _session_dto_for(session, chat)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: UUID, body: UpdateRequest,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Correct the auto-extracted company / role title / track. Changing the track
    re-matches the CV and re-runs the ATS + prompts."""
    chat = await _owned_chat(session, principal, session_id)
    if body.company is not None:
        chat.company = body.company.strip() or None
    if body.role_title is not None:
        chat.role_title = body.role_title.strip() or chat.role_title
    if body.track is not None and body.track != chat.track:
        chat.track = body.track
        await service.reanalyze(session, chat=chat)
        breakdown = dict(chat.ats_breakdown or {})
        breakdown["track_match"] = {
            "track": chat.track.value,
            "method": "manual",
            "reason": "Track selected manually on job details.",
        }
        chat.ats_breakdown = breakdown
    await session.flush()
    return await _session_dto_for(session, chat)


@router.post("/sessions/{session_id}/facts")
async def add_fact(
    session_id: UUID, body: FactRequest,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Add a known-true skill the JD didn't surface (truth-bounded)."""
    chat = await _owned_chat(session, principal, session_id)
    await service.add_confirmed_fact(session, chat=chat, skill=body.skill)
    return await _session_dto_for(session, chat)


@router.post("/sessions/{session_id}/vet-gaps")
async def vet_gaps(
    session_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """AI-review rule-based gap prompts and replace unresolved skill confirmations."""
    chat = await _owned_chat(session, principal, session_id)
    prompts = await service.vet_gaps_with_ai(session, chat=chat)
    return await _session_dto(session, chat, prompts)


@router.post("/sessions/{session_id}/generate")
async def generate(
    session_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    chat = await _owned_chat(session, principal, session_id)
    application = await service.generate_application(
        session, user_id=chat.user_id, chat_session_id=session_id
    )
    return {"application_id": str(application.id), "job_id": str(application.job_id)}


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: UUID,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    chat = await _owned_chat(session, principal, session_id)
    return await _session_dto_for(session, chat)

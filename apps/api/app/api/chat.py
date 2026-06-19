"""Manual application chatbot API (dashboard-rich; WhatsApp-lite shares the engine)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PrincipalType
from app.core.errors import DomainError, NotFoundError
from app.db import get_session
from app.deps import Principal, authorize_owner, current_principal, scoped_user_ids
from app.models.chat import ChatPrompt, ChatSession
from app.pipelines.manual import service

router = APIRouter(prefix="/chat", tags=["chat"])


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
    return {"id": str(p.id), "question": p.question, "options": p.options,
            "kind": p.kind.value, "selected": p.selected, "resolved": p.resolved}


def _session_dto(chat: ChatSession, prompts: list[ChatPrompt]) -> dict:
    return {
        "session_id": str(chat.id), "state": chat.state.value,
        "track": chat.track.value if chat.track else None,
        "role_title": chat.role_title,
        "role_cv_matched": chat.role_cv_id is not None,
        "ats": {"score": chat.ats_score, "breakdown": chat.ats_breakdown},
        "job_id": str(chat.job_id) if chat.job_id else None,
        "prompts": [_prompt_dto(p) for p in prompts],
    }


async def _owned_chat(session, principal: Principal, session_id: UUID) -> ChatSession:
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise NotFoundError("Chat session not found")
    await authorize_owner(session, principal, chat.user_id)
    return chat


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
    return _session_dto(chat, prompts)


@router.post("/sessions/{session_id}/answer")
async def answer(
    session_id: UUID, body: AnswerRequest,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    chat = await _owned_chat(session, principal, session_id)
    prompt = await service.answer_prompt(
        session, user_id=chat.user_id, prompt_id=body.prompt_id,
        selected=body.selected, detail=body.detail,
    )
    return {"ok": True, "resolved": prompt.resolved}


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
    prompts = list((await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
    )).scalars().all())
    return _session_dto(chat, prompts)

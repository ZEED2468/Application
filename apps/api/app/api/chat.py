"""Manual application chatbot API (dashboard-rich; WhatsApp-lite shares the engine)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db import get_session
from app.deps import current_user
from app.models.chat import ChatPrompt, ChatSession
from app.models.user import User
from app.pipelines.manual import service

router = APIRouter(prefix="/chat", tags=["chat"])


class StartRequest(BaseModel):
    jd_text: str
    va_id: UUID | None = None
    surface: str = "dashboard"


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


@router.post("/sessions")
async def start(
    body: StartRequest,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    chat, prompts = await service.start_session(
        session, user_id=user.id, jd_text=body.jd_text, va_id=body.va_id, surface=body.surface
    )
    return _session_dto(chat, prompts)


@router.post("/sessions/{session_id}/answer")
async def answer(
    session_id: UUID, body: AnswerRequest,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    prompt = await service.answer_prompt(
        session, user_id=user.id, prompt_id=body.prompt_id,
        selected=body.selected, detail=body.detail,
    )
    return {"ok": True, "resolved": prompt.resolved}


@router.post("/sessions/{session_id}/generate")
async def generate(
    session_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    application = await service.generate_application(
        session, user_id=user.id, chat_session_id=session_id
    )
    return {"application_id": str(application.id), "job_id": str(application.job_id)}


@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: UUID,
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    chat = await session.get(ChatSession, session_id)
    if chat is None or chat.user_id != user.id:
        raise NotFoundError("Chat session not found")
    prompts = list((await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
    )).scalars().all())
    return _session_dto(chat, prompts)

"""chat_session + chat_prompt — the manual VA-driven application conversation.

A VA pastes a JD; the bot matches a role_cv, runs the ATS comparison, and raises
confirm-true prompts. Selections feed CV tailoring ONLY when confirmed true — the
truth boundary is enforced here as well as in the generation engine.
"""

import uuid

from sqlalchemy import Boolean, Enum, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ChatPromptKind, ChatState, Track
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_session"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()  # whose hunt this application is for
    va_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("va.id", ondelete="SET NULL"), nullable=True  # who is driving
    )
    surface: Mapped[str] = mapped_column(String(16), default="dashboard", nullable=False)
    state: Mapped[ChatState] = mapped_column(
        Enum(ChatState, native_enum=False), default=ChatState.started, nullable=False
    )
    jd_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    jd_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    track: Mapped[Track | None] = mapped_column(Enum(Track, native_enum=False), nullable=True)
    role_cv_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("role_cv.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("job.id", ondelete="SET NULL"), nullable=True
    )
    ats_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ats_breakdown: Mapped[dict] = mapped_column(JsonB, default=dict)
    # Facts the VA has confirmed TRUE during the chat; merged into the tailoring input.
    confirmed_facts: Mapped[list] = mapped_column(JsonB, default=list)


class ChatPrompt(Base, TimestampMixin):
    __tablename__ = "chat_prompt"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    chat_session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ChatPromptKind] = mapped_column(
        Enum(ChatPromptKind, native_enum=False), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list] = mapped_column(JsonB, default=list)
    selected: Mapped[list] = mapped_column(JsonB, default=list)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

"""The 6 frozen event payload schemas — the inter-team API.

Every payload carries `user_id`. These pydantic models are validated at the
bus boundary; the JSON fixtures in ./fixtures must validate against them (CI gate).
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.core.enums import Track
from app.events.names import (
    APPLICATION_SUBMITTED,
    CHAT_APPLICATION_CREATED,
    CHAT_CV_MATCHED,
    CHAT_PROMPTS_RAISED,
    CHAT_SESSION_STARTED,
    CV_GENERATED,
    JOB_DISCOVERED,
    JOB_SCORED,
    OUTREACH_SENT,
    REPLY_RECEIVED,
)


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID


class JobDiscovered(EventPayload):
    job_id: UUID
    source: str


class JobScored(EventPayload):
    job_id: UUID
    relevance_score: float
    track: Track


class CvGenerated(EventPayload):
    job_id: UUID
    generated_cv_id: UUID


class ApplicationSubmitted(EventPayload):
    application_id: UUID
    job_id: UUID
    track: Track


class OutreachSent(EventPayload):
    outreach_id: UUID
    application_id: UUID
    contact_id: UUID


class ReplyReceived(EventPayload):
    reply_id: UUID
    thread_id: UUID


# --- Manual (VA chatbot) path ---


class ChatSessionStarted(EventPayload):
    chat_session_id: UUID


class ChatCvMatched(EventPayload):
    chat_session_id: UUID
    role_cv_id: UUID
    track: Track


class ChatPromptsRaised(EventPayload):
    chat_session_id: UUID
    prompt_count: int


class ChatApplicationCreated(EventPayload):
    chat_session_id: UUID
    application_id: UUID
    job_id: UUID


# Event name -> schema. Used by the bus and the contract test.
CONTRACTS: dict[str, type[EventPayload]] = {
    JOB_DISCOVERED: JobDiscovered,
    JOB_SCORED: JobScored,
    CV_GENERATED: CvGenerated,
    APPLICATION_SUBMITTED: ApplicationSubmitted,
    OUTREACH_SENT: OutreachSent,
    REPLY_RECEIVED: ReplyReceived,
    CHAT_SESSION_STARTED: ChatSessionStarted,
    CHAT_CV_MATCHED: ChatCvMatched,
    CHAT_PROMPTS_RAISED: ChatPromptsRaised,
    CHAT_APPLICATION_CREATED: ChatApplicationCreated,
}

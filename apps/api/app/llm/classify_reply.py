"""Reply classification — routine (scheduling/ack) vs substantive (screening,
negotiation, real conversation). One cheap call. Routine replies get an
auto-draft; substantive ones get context only (the VA writes)."""

from __future__ import annotations

from app.core.enums import ReplyClassification

_ROUTINE_SIGNALS = (
    "schedule", "calendar", "availability", "time work", "book a", "confirm",
    "thanks", "thank you", "received", "got it", "noted", "out of office",
)


def _fake_classify(body: str) -> tuple[ReplyClassification, str | None]:
    low = (body or "").lower()
    if any(s in low for s in _ROUTINE_SIGNALS):
        draft = (
            "Thanks for getting back to me — happy to work around your schedule. "
            "I'm generally free weekday afternoons (your timezone); send a couple of "
            "slots and I'll confirm."
        )
        return ReplyClassification.routine, draft
    return ReplyClassification.substantive, None


async def classify(body: str) -> tuple[ReplyClassification, str | None]:
    from app.llm import client

    if not client.is_live("classify_reply"):
        return _fake_classify(body)

    system = (
        "Classify this inbound email reply as `routine` (scheduling/ack) or "
        "`substantive` (screening/negotiation/real conversation). If routine, also "
        "propose a brief reply draft. Return: routine|substantive || <draft or empty>."
    )
    text = await client.complete_text(system, body, max_tokens=400, feature="classify_reply")
    label, _, draft = text.partition("||")
    cls = (ReplyClassification.routine if "routine" in label.lower()
           else ReplyClassification.substantive)
    return cls, (draft.strip() or None if cls is ReplyClassification.routine else None)

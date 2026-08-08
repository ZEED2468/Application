"""The TRUE_GAP bridge — classify required slots, raise prompt-cards, resume on answers.

Slice 7. This module is the ONLY place the CV engine touches the chat aggregate. A required slot
that is absent and not inferable becomes a real `ChatPrompt` (kind=missing_section) on a
`ChatSession` linked to the run (`cv_run_id`). The VA answers through the existing
`POST /chat/sessions/{id}/answer` endpoint; when every gap prompt on the session is resolved, the
answers merge into the run's cv_json and the pipeline re-coordinates from the top.

Chat models + the machine are imported lazily (inside the functions that need them) so the machine
can import this module at the top without a cycle.
"""

from __future__ import annotations

import copy
import re

from app.cv_engine.templates.library import slot_present
from app.cv_engine.templates.spec import TemplateSpec

# The one required slot the engine can fill from the candidate's own history (Slice 7's INFERABLE).
INFERABLE = {"summary"}

# What the VA is asked when a required slot is a genuine gap (rendered in the prompt-card).
_GAP_QUESTION = {
    "experience": ("Your CV has no work experience yet. Add at least one role — the title, the "
                   "company, and a few bullet points of what you did."),
    "skills": "Your CV lists no skills. What are your key skills? (comma-separated)",
    "contact": "Your CV has no contact link. Add a GitHub, LinkedIn, or email.",
    "summary": "Add a short professional summary (2-3 lines).",
}


def classify(spec: TemplateSpec | None, cv_json: dict) -> dict[str, str]:
    """Per REQUIRED slot: FILLED | INFERABLE | TRUE_GAP."""
    verdicts: dict[str, str] = {}
    for s in (spec.required_slots() if spec else ()):
        if slot_present(s.id, cv_json):
            verdicts[s.id] = "FILLED"
        elif s.id in INFERABLE:
            verdicts[s.id] = "INFERABLE"
        else:
            verdicts[s.id] = "TRUE_GAP"
    return verdicts


def gap_slots(spec: TemplateSpec | None, cv_json: dict) -> list[str]:
    """Required slots that are absent, NOT inferable, and must be asked (absence_ok ask|block)."""
    out: list[str] = []
    for s in (spec.required_slots() if spec else ()):
        if s.id in INFERABLE or slot_present(s.id, cv_json):
            continue
        if s.absence_ok in ("ask", "block"):
            out.append(s.id)
    return out


async def raise_gap_prompts(session, run, slots: list[str]):
    """Find-or-create the run's ChatSession, add a missing_section prompt per unasked gap slot."""
    from sqlalchemy import select

    from app.core.enums import ChatPromptKind, ChatState
    from app.models.chat import ChatPrompt, ChatSession

    chat = (await session.execute(
        select(ChatSession).where(ChatSession.cv_run_id == run.id)
    )).scalars().first()
    if chat is None:
        chat = ChatSession(
            user_id=run.user_id, cv_run_id=run.id, surface="cv_engine",
            state=ChatState.prompts_raised, confirmed_facts=[],
        )
        session.add(chat)
        await session.flush()
    # An unresolved prompt already covers a slot -> don't duplicate it.
    open_slots = {p.slot for p in (await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
    )).scalars().all() if not p.resolved}
    for sid in slots:
        if sid in open_slots:
            continue
        session.add(ChatPrompt(
            user_id=run.user_id, chat_session_id=chat.id,
            kind=ChatPromptKind.missing_section, slot=sid,
            question=_GAP_QUESTION.get(sid, f"Your CV is missing its {sid}. Please provide it."),
            options=[],
        ))
    await session.flush()
    return chat


def _link_label(url: str) -> str:
    u = (url or "").lower()
    if "github" in u:
        return "github"
    if "linkedin" in u:
        return "linkedin"
    if "@" in u:
        return "email"
    return "website"


def merge_answer(cv_json: dict, slot: str, text: str) -> dict:
    """Splice a resolved gap answer into the right cv_json section (returns a new dict)."""
    cv = copy.deepcopy(cv_json)
    text = (text or "").strip()
    if not text:
        return cv
    if slot == "summary":
        cv["summary"] = text
    elif slot == "skills":
        cv["skills"] = [s.strip() for s in re.split(r"[,\n]", text) if s.strip()]
    elif slot == "contact":
        links = dict(cv.get("links") or {})
        links[_link_label(text)] = text
        cv["links"] = links
    elif slot == "experience":
        bullets = [b.strip() for b in text.split("\n") if b.strip()] or [text]
        entry = {"title": "", "company": "", "bullets": bullets}
        cv["experience"] = [*(cv.get("experience") or []), entry]
    return cv


async def resume_if_ready(session, *, chat_session_id):
    """Resume the run once every gap prompt on its session is answered (else no-op).

    Merges each resolved answer into the run's cv_json (skipping any slot already filled, so a
    re-suspend never double-merges), clears needs_input, and re-coordinates from the top."""
    from sqlalchemy import select

    from app.core.enums import ChatState, RunState
    from app.cv_engine.runs.models import CvRun
    from app.models.chat import ChatPrompt, ChatSession

    chat = await session.get(ChatSession, chat_session_id)
    if chat is None or chat.cv_run_id is None:
        return None
    prompts = list((await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
    )).scalars().all())
    if not prompts or not all(p.resolved for p in prompts):
        return None
    run = await session.get(CvRun, chat.cv_run_id)
    if run is None or run.state is not RunState.needs_input:
        return None

    cv = (run.input or {}).get("cv_json") or {}
    for p in prompts:
        answer = (p.detail or "").strip() or " ".join(p.selected or [])
        if p.slot and answer and not slot_present(p.slot, cv):
            cv = merge_answer(cv, p.slot, answer)
    run.input = {**(run.input or {}), "cv_json": cv}
    run.needs_input = None
    chat.state = ChatState.ready
    await session.flush()

    from app.cv_engine.runs.machine import coordinate
    return await coordinate(session, run)

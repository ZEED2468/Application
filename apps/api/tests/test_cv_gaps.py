"""TRUE_GAP suspension + INFERABLE slot filling (Slice 7).

Offline: a complete CV runs as before, and a missing (but inferable) summary just surfaces
downstream — never an ask. Live inference: a missing summary is composed from the ledger and kept
only if it clears the grounding seal + the supports judge. Deterministic suspend: a missing,
non-inferable required slot (skills) raises a real prompt-card on a run-linked ChatSession, and
answering it through the chat service resumes the run.
"""

import json
from uuid import UUID

from sqlalchemy import select

from app.core.enums import ChatPromptKind, RunState
from app.cv_engine.runs.machine import run_pipeline
from app.cv_engine.runs.models import CvRunStep
from app.llm import client
from app.models.chat import ChatPrompt, ChatSession
from app.pipelines.manual import service
from tests.helpers import seed_hunter

_LIVE = {"cv_infer", "cv_infer_verify"}   # inference live; repair/judge stay offline


def _cv(*, summary="Backend engineer building production systems in Go.",
        skills=("Go", "Postgres"), contact=True):
    cv: dict = {"headline": "Backend Engineer"}
    if summary:
        cv["summary"] = summary
    if skills:
        cv["skills"] = list(skills)
    cv["experience"] = [{
        "title": "Backend Engineer", "company": "Streamline", "dates": "2020 -- 2024",
        "bullets": ["Built Go microservices", "Ran Postgres in production"],
    }]
    cv["links"] = {"github": "https://github.com/adahunter"} if contact else {}
    return cv


def _input(cv):
    # No explicit ledger → derived from cv_json (so inference has real role/skill facts).
    return {"cv_json": cv, "jd_text": "Go Postgres backend", "role_title": "Backend Engineer",
            "name": "Ada Hunter"}


def _canned(summary, *, supported=True):
    async def _fn(system, prompt, **k):
        if "professional summary" in system:              # infer_summary
            return json.dumps({"summary": summary})
        if "strict fact-checker" in system:               # supports — door #2
            return json.dumps({"supported": bool(supported)})
        return None
    return _fn


def _go_live(monkeypatch, canned):
    monkeypatch.setattr(client, "is_live", lambda feature=None: feature in _LIVE)
    monkeypatch.setattr(client, "try_complete_text", canned)


async def test_missing_skills_suspends_to_needs_input(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv(skills=())))

    assert run.state is RunState.needs_input
    assert run.needs_input and "skills" in run.needs_input["slots"]
    assert not run.artifact_ref                            # a suspended run renders nothing
    chat = await session.get(ChatSession, UUID(run.needs_input["session_id"]))
    assert chat is not None and chat.cv_run_id == run.id
    assert chat.user_id == user.id and chat.va_id is None  # standalone run: keyed by its own user
    prompts = (await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == chat.id)
    )).scalars().all()
    assert any(p.kind is ChatPromptKind.missing_section and p.slot == "skills" for p in prompts)


async def test_answering_the_gap_resumes_the_run(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv(skills=())))
    assert run.state is RunState.needs_input

    prompt = (await session.execute(
        select(ChatPrompt).where(
            ChatPrompt.chat_session_id == UUID(run.needs_input["session_id"]),
            ChatPrompt.slot == "skills",
        )
    )).scalars().first()
    await service.answer_prompt(
        session, user_id=user.id, prompt_id=prompt.id, selected=[], detail="Go, Python, SQL"
    )

    assert run.state is not RunState.needs_input           # the pipeline resumed
    assert run.needs_input is None
    assert run.input["cv_json"]["skills"] == ["Go", "Python", "SQL"]


async def test_inferred_summary_is_filled_not_asked(session, monkeypatch):
    user, _ = await seed_hunter(session)
    _go_live(monkeypatch, _canned(
        "Backend engineer with Go and Postgres experience at Streamline."))
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv(summary="")))

    assert run.state is not RunState.needs_input           # inferred, never asked
    assert (run.input["cv_json"].get("summary") or "").strip()
    step = (await session.execute(
        select(CvRunStep).where(
            CvRunStep.run_id == run.id, CvRunStep.prompt_version == "cv_infer.v1"
        )
    )).scalars().first()
    assert step is not None


async def test_ungrounded_inference_is_rejected(session, monkeypatch):
    user, _ = await seed_hunter(session)
    # The judge is fooled (supported=True), but "300%" is nowhere in the history — grounding drops.
    _go_live(monkeypatch, _canned(
        "Backend engineer who boosted revenue by 300% at Streamline.", supported=True,
    ))
    run = await run_pipeline(session, user_id=user.id, input=_input(_cv(summary="")))

    assert "300" not in (run.input["cv_json"].get("summary") or "")
    assert not (run.input["cv_json"].get("summary") or "").strip()   # nothing landed


async def test_offline_gap_is_a_no_op(session):
    user, _ = await seed_hunter(session)
    complete = await run_pipeline(session, user_id=user.id, input=_input(_cv()))
    assert complete.state is not RunState.needs_input and complete.needs_input is None

    # A missing summary is INFERABLE, so offline it surfaces downstream — it is NOT an ask.
    no_summary = await run_pipeline(session, user_id=user.id, input=_input(_cv(summary="")))
    assert no_summary.state is not RunState.needs_input
    assert not (no_summary.input["cv_json"].get("summary") or "").strip()

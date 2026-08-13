"""JD-coverage gaps: the engine asks the candidate to confirm a JD-critical skill their profile
lacks (mid-flight prompt-cards), rather than letting the model invent it.

Gated by `input["ask_coverage_gaps"]` (only the workspace Generate sets it). A confirmed "Yes" adds
the skill; a "No" leaves it honestly absent — and, crucially, is never re-asked on resume (the loop
guard). Standalone-engine tests: no job, so no GeneratedCv re-map (covered in test_generation_engine).
"""

from uuid import UUID

from sqlalchemy import select

from app.core.enums import ChatPromptKind, RunState
from app.cv_engine.runs.machine import run_pipeline
from app.models.chat import ChatPrompt, ChatSession
from app.pipelines.manual import service
from tests.helpers import seed_hunter

# Emphasis-marked ("required") critical the seeded profile lacks (Kafka), plus one it has (Go).
_JD = "Backend Engineer. Kafka is required. Strong Go experience is essential."


def _cv():
    return {
        "headline": "Backend Engineer",
        "summary": "Backend engineer building production systems in Go.",
        "skills": ["Go", "Postgres"],
        "experience": [{
            "title": "Backend Engineer", "company": "Streamline", "dates": "2020 -- 2024",
            "bullets": ["Built Go microservices", "Ran Postgres in production"],
        }],
        "links": {"github": "https://github.com/adahunter"},
    }


def _input(*, ask: bool):
    # No explicit ledger → derived from cv_json (Go/Postgres/Streamline are the real facts).
    inp = {"cv_json": _cv(), "jd_text": _JD, "role_title": "Backend Engineer", "name": "Ada Hunter"}
    if ask:
        inp["ask_coverage_gaps"] = True
    return inp


async def _prompts(session, run) -> list[ChatPrompt]:
    return list((await session.execute(
        select(ChatPrompt).where(
            ChatPrompt.chat_session_id == UUID(run.needs_input["session_id"]))
    )).scalars().all())


async def test_coverage_gap_suspends_with_a_skill_prompt(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(ask=True))

    assert run.state is RunState.needs_input
    assert [s.lower() for s in run.needs_input["slots"]] == ["kafka"]   # Go is owned → not asked
    chat = await session.get(ChatSession, UUID(run.needs_input["session_id"]))
    assert chat is not None and chat.cv_run_id == run.id
    prompts = await _prompts(session, run)
    assert any(p.kind is ChatPromptKind.missing_skill_confirm and (p.slot or "").lower() == "kafka"
               for p in prompts)
    assert not run.artifact_ref                                         # suspended → no artifact


async def test_no_coverage_ask_without_the_flag(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(ask=False))
    # Best-effort: the same JD gap is noted but never stops the run.
    assert run.state is not RunState.needs_input


async def test_declining_a_coverage_gap_does_not_reask(session):
    # The loop guard: a declined skill stays a gap forever, so it must NOT be re-asked on resume —
    # else the run would re-suspend on every re-coordinate.
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(ask=True))
    assert run.state is RunState.needs_input
    prompt = (await _prompts(session, run))[0]

    await service.answer_prompt(
        session, user_id=user.id, prompt_id=prompt.id, selected=["No"], detail="")

    assert run.state is not RunState.needs_input and run.needs_input is None
    prompts = list((await session.execute(
        select(ChatPrompt).where(ChatPrompt.chat_session_id == prompt.chat_session_id)
    )).scalars().all())
    assert len(prompts) == 1 and prompts[0].resolved            # no new prompt raised
    assert "kafka" not in [s.lower() for s in run.input["cv_json"]["skills"]]


async def test_confirming_a_coverage_gap_adds_the_skill(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_input(ask=True))
    prompt = (await _prompts(session, run))[0]

    await service.answer_prompt(
        session, user_id=user.id, prompt_id=prompt.id,
        selected=["Yes — I have it"], detail="Ran Kafka pipelines at Streamline")

    assert run.state is not RunState.needs_input and run.needs_input is None
    assert "kafka" in [s.lower() for s in run.input["cv_json"]["skills"]]

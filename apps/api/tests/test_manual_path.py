"""Manual VA-chatbot path + the cross-cutting tracker-sync guarantee."""

import pytest
from sqlalchemy import select

from app.core.enums import ApplicationStatus, ChatState, Origin
from app.events import names
from app.models.application import Application
from app.models.application_event import ApplicationEvent
from app.models.cover_letter import CoverLetter
from app.models.generated_cv import GeneratedCv
from app.pipelines.manual import service
from tests.helpers import EventSink, seed_hunter

JD = """Senior Backend Engineer at Streamline
We need someone strong in Go, Kubernetes, microservices and Kafka to build
distributed systems. Postgres experience required.
"""


@pytest.mark.asyncio
async def test_manual_chatbot_full_flow_creates_identical_objects(session):
    user, _ = await seed_hunter(session)
    sink = EventSink()

    # 1. Paste JD -> session, matched CV, ATS, prompts.
    chat, prompts = await service.start_session(
        session, user_id=user.id, jd_text=JD, emit=sink
    )
    assert chat.ats_score is not None
    assert chat.track is not None
    assert names.CHAT_SESSION_STARTED in sink.names()
    assert names.CHAT_PROMPTS_RAISED in sink.names()
    # Kafka is missing from the profile -> a confirm-true prompt was raised.
    assert any("kafka" in p.question.lower() for p in prompts)

    # 2. VA confirms Kafka is genuinely true.
    kafka_prompt = next(p for p in prompts if "kafka" in p.question.lower())
    await service.answer_prompt(
        session, user_id=user.id, prompt_id=kafka_prompt.id,
        selected=["Yes — add it (true)"], detail="Kafka",
    )
    chat = await session.get(type(chat), chat.id)
    assert "Kafka" in (chat.confirmed_facts or [])

    # 3. Generate -> identical job/cv/cover/application objects.
    application = await service.generate_application(
        session, user_id=user.id, chat_session_id=chat.id, emit=sink
    )
    assert application.status is ApplicationStatus.submitted
    assert names.CHAT_APPLICATION_CREATED in sink.names()
    # Same seam into Pipeline B as the autonomous path.
    assert names.APPLICATION_SUBMITTED in sink.names()
    assert names.CV_GENERATED in sink.names()

    cv = (await session.execute(
        select(GeneratedCv).where(GeneratedCv.job_id == application.job_id)
    )).scalar_one()
    cover = (await session.execute(
        select(CoverLetter).where(CoverLetter.job_id == application.job_id)
    )).scalar_one()
    assert cv.ats_score is not None and cv.source_role_cv_id is None
    assert cover.body and len([p for p in cover.body.split("\n\n") if p.strip()]) == 3

    # The confirmed-true Kafka fact made it into the tailored CV (truth-bounded).
    assert "kafka" in str(cv.cv_json).lower()


@pytest.mark.asyncio
async def test_manual_application_is_visible_to_tracker_with_audit(session):
    """No path may create an application the tracker can't see."""
    user, _ = await seed_hunter(session)
    chat, _ = await service.start_session(session, user_id=user.id, jd_text=JD, emit=EventSink())
    application = await service.generate_application(
        session, user_id=user.id, chat_session_id=chat.id, emit=EventSink()
    )

    # Tracker query (same as the dashboard) sees the manual application.
    tracked = (await session.execute(
        select(Application).where(Application.user_id == user.id)
    )).scalars().all()
    assert any(a.id == application.id for a in tracked)

    # Origin is manual; an audit 'created' event exists.
    events = (await session.execute(
        select(ApplicationEvent).where(ApplicationEvent.application_id == application.id)
    )).scalars().all()
    kinds = {e.kind for e in events}
    assert "created" in kinds
    created = next(e for e in events if e.kind == "created")
    assert created.detail.get("origin") == "manual"

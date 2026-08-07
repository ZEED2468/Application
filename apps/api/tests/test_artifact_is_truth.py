"""Invariant #2 — the artifact is the truth; a missing measurement is never a pass.

With a compiler, a clean run compiles a real PDF and releases with a real score. With no
compiler, the gate is `unevaluated` and the run ends at needs_review with no number and no
stored artifact — the honest degraded path, not a silent pass.
"""

import json
from pathlib import Path

import pytest

from app.cv_engine.render.compile import has_compiler
from app.cv_engine.runs.machine import run_pipeline
from tests.helpers import seed_hunter

FIX_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "cv_engine"


def _clean_input() -> dict:
    return json.loads((FIX_DIR / "clean.json").read_text(encoding="utf-8"))["input"]


async def test_no_compiler_is_unevaluated_not_released(session, monkeypatch):
    # Simulate an environment with no LaTeX engine — the stub must NOT count as ready.
    monkeypatch.setattr("app.cv_engine.render.compile.has_compiler", lambda: False)
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_clean_input())
    assert run.state.value == "needs_review"
    assert run.score is None
    assert run.artifact_ref is None


@pytest.mark.skipif(not has_compiler(), reason="needs tectonic")
async def test_with_compiler_clean_releases_with_a_real_score(session):
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_clean_input())
    assert run.state.value == "released"
    assert run.score is not None
    assert run.artifact_ref


@pytest.mark.skipif(not has_compiler(), reason="needs tectonic")
async def test_verified_step_scores_the_reextracted_artifact(session):
    """The score comes from the re-extracted PDF text through the gate — the verified
    step records the gate as `pass` for a clean artifact."""
    from sqlalchemy import select

    from app.core.enums import RunState
    from app.cv_engine.runs.models import CvRunStep

    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_clean_input())
    verified = (
        await session.execute(
            select(CvRunStep).where(
                CvRunStep.run_id == run.id, CvRunStep.state == RunState.verified
            )
        )
    ).scalar_one()
    assert verified.detail["gate"]["status"] == "pass"
    assert verified.detail["score"] is not None

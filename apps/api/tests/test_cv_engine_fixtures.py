"""Golden fixtures for the CV-engine spine — (input → expected verdict) pairs.

Mirrors the event-contract golden pattern: one JSON per case, a parametrized runner,
and a completeness check that every fixture is exercised. Grows one fixture per real bug
(target ~30). Draft-phase verdicts (grounding/structure) are compiler-independent; the
clean case's terminal state depends on whether a real PDF could be compiled.
"""

import json
from pathlib import Path

import pytest

from app.cv_engine.render.compile import has_compiler
from app.cv_engine.runs.machine import run_pipeline
from tests.helpers import seed_hunter

FIX_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "cv_engine"
FIXTURES = sorted(FIX_DIR.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _blocking_ids(run) -> set[str]:
    return {v["rule_id"] for v in run.violations if v["severity"] in ("critical", "major")}


@pytest.mark.parametrize("path", FIXTURES, ids=[p.stem for p in FIXTURES])
async def test_cv_engine_fixture(session, path):
    user, _ = await seed_hunter(session)
    fx = _load(path)
    run = await run_pipeline(session, user_id=user.id, input=fx["input"])
    exp = fx["expect"]
    blocking = _blocking_ids(run)

    if exp.get("suspends"):
        # A missing required, non-inferable slot suspends to NEEDS_INPUT before render (Slice 7).
        assert run.state.value == "needs_input", f"{path.stem}: expected suspension"
        assert set(exp["suspends"]) <= set((run.needs_input or {}).get("slots", [])), (
            f"{path.stem}: expected gaps {exp['suspends']}, got {run.needs_input}"
        )
        assert not run.artifact_ref, "a suspended run renders no artifact"
        return

    if exp["clean"]:
        assert not blocking, f"clean fixture produced blocking violations: {blocking}"
        if has_compiler():
            # A real artifact compiled + verified → released with a real score.
            assert run.state.value == "released"
            assert run.score is not None
            assert run.artifact_ref
        else:
            # No compiler → the artifact is unevaluated, never a pass.
            assert run.state.value == "needs_review"
            assert run.score is None
    else:
        # A blocking violation ends the run at needs_review regardless of the compiler.
        assert run.state.value == "needs_review"
        assert set(exp["blocking"]) <= blocking, (
            f"{path.stem}: expected {exp['blocking']} within blocking {blocking}"
        )

    # Optional PATCH-phase assertions (compiler-independent — fixes run before render).
    if "fixed_min" in exp:
        assert len(run.delta.get("fixed", [])) >= exp["fixed_min"], (
            f"{path.stem}: expected >= {exp['fixed_min']} fixes, got {run.delta.get('fixed')}"
        )
    if "resolved" in exp:
        assert set(exp["resolved"]) <= set(run.delta.get("resolved", [])), (
            f"{path.stem}: expected {exp['resolved']} resolved, got {run.delta.get('resolved')}"
        )


def test_every_fixture_exercised():
    assert FIXTURES, "no cv_engine fixtures found"
    for path in FIXTURES:
        fx = _load(path)
        assert {"input", "expect"} <= fx.keys(), f"{path.name} missing input/expect"
        assert "clean" in fx["expect"], f"{path.name} expect missing 'clean'"
        assert "cv_json" in fx["input"], f"{path.name} input missing cv_json"


async def test_clean_cv_still_emits_a_delta(session):
    """A clean CV skips PATCH but must still emit a delta report (guards the clean path)."""
    user, _ = await seed_hunter(session)
    run = await run_pipeline(session, user_id=user.id, input=_load(FIX_DIR / "clean.json")["input"])
    assert isinstance(run.delta, dict)
    assert {"failed", "blocking", "violation_count"} <= run.delta.keys()
    assert run.delta["violation_count"] == 0
    assert run.delta["failed"] == [] and run.delta["blocking"] == []

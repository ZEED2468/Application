"""Provenance closure (invariant #9): every number in the RENDERED artifact traces
back to the ledger. This is the CI seal that content cannot originate from a third
source — proven on the real compiled PDF, not hoped for.

Skipped when no tectonic is available (there is no real artifact to inspect); it runs
in the Docker test image and on any host with tectonic installed.
"""

import json
from pathlib import Path

import pytest

from app.cv_engine.render.compile import has_compiler
from app.cv_engine.render.extract import extract_pdfminer, extract_pypdf
from app.cv_engine.rules.grounding import _NUMBER, _ledger_text, _num, _numbers
from app.cv_engine.runs.machine import run_pipeline
from app.integrations import r2
from tests.helpers import seed_hunter

FIX_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "cv_engine"


@pytest.mark.skipif(not has_compiler(), reason="needs tectonic to produce a real artifact")
async def test_every_number_in_the_artifact_traces_to_the_ledger(session):
    user, _ = await seed_hunter(session)
    fx = json.loads((FIX_DIR / "clean.json").read_text(encoding="utf-8"))
    run = await run_pipeline(session, user_id=user.id, input=fx["input"])
    assert run.state.value == "released" and run.artifact_ref

    pdf = await r2.get_bytes(run.artifact_ref)
    assert pdf, "the compiled artifact was not retrievable from storage"
    text = f"{extract_pypdf(pdf)}\n{extract_pdfminer(pdf)}"

    allowed = _numbers(_ledger_text(fx["input"]["ledger"]))
    in_artifact = {_num(m.group(0)) for m in _NUMBER.finditer(text)}
    stray = in_artifact - allowed
    assert not stray, f"artifact contains numbers absent from the ledger: {sorted(stray)}"


async def test_every_change_and_edge_traces_to_the_ledger(session):
    """Provenance closure over the change graph (Slice 8): every change cites, and every
    `derived_from` edge points at, a real ledger fact — a change can never originate from a
    third source. Compiler-independent (the delta + ledger are set before render)."""
    user, _ = await seed_hunter(session)
    fx = json.loads((FIX_DIR / "messy_dates.json").read_text(encoding="utf-8"))
    run = await run_pipeline(session, user_id=user.id, input=fx["input"])

    fact_ids = {f["id"] for f in run.ledger_snapshot["facts"]}
    assert fact_ids
    for rec in run.delta.get("fixed", []):
        assert set(rec.get("source") or []) <= fact_ids, f"change cites a non-ledger source: {rec}"
    for f in run.ledger_snapshot["facts"]:
        assert set(f.get("derived_from") or []) <= fact_ids, f"edge to a non-ledger fact: {f}"

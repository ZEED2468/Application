"""Template API + resolution — list, bind (built-in + custom), and that a bound template
drives + pins a run. Exercises the route functions directly.
"""

import io
import json
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

from app.api.cv_templates import (
    BindBody,
    bind_template,
    list_templates,
    preview_template,
    upload_template,
)
from app.core.enums import Track
from app.cv_engine.render.compile import has_compiler
from app.cv_engine.runs.machine import run_pipeline
from tests.helpers import seed_hunter

FIX = json.loads(
    (Path(__file__).resolve().parent.parent / "fixtures" / "cv_engine" / "clean.json").read_text()
)["input"]

GOOD_TEX = (
    r"\documentclass{article}\usepackage[margin=0.9in]{geometry}\begin{document}"
    "\n%%CV:HEADER%%\n%%CV:SUMMARY%%\n%%CV:SKILLS%%\n%%CV:EXPERIENCE%%\n"
    r"\end{document}"
)


async def test_list_includes_builtins_and_bound_is_none(session):
    user, _ = await seed_hunter(session)
    res = await list_templates(track="backend", user=user, session=session)
    ids = {t["id"] for t in res["templates"]}
    assert {"canonical", "compact", "academic"} <= ids
    assert res["bound"] is None


async def test_bind_builtin_drives_and_pins_a_run(session):
    user, _ = await seed_hunter(session)  # backend profile
    await bind_template(BindBody(track=Track.backend, template_id="compact"), user, session)

    run = await run_pipeline(session, user_id=user.id, input={**FIX})
    assert run.template_id == "compact"  # the bound built-in was resolved + pinned


@pytest.mark.skipif(not has_compiler(), reason="upload validation compiles a dummy render")
async def test_upload_bind_and_run_uses_custom_template(session):
    user, _ = await seed_hunter(session)
    up = UploadFile(filename="mine.tex", file=io.BytesIO(GOOD_TEX.encode("utf-8")))
    res = await upload_template(track="backend", name="Mine", file=up, user=user, session=session)
    slot_ids = {s["id"] for s in res["slots"]}
    assert res["source"] == "custom" and {"summary", "experience"} <= slot_ids

    await bind_template(BindBody(track=Track.backend, template_id=res["id"]), user, session)
    run = await run_pipeline(session, user_id=user.id, input={**FIX})
    assert run.template_id == res["id"]  # the custom template drove + pinned the run

    # Preview renders the custom template with sample content.
    resp = await preview_template(res["id"], user=user, session=session)
    assert resp.media_type == "application/pdf" and resp.body[:4] == b"%PDF"

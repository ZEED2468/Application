"""CV regeneration honors the uploaded LaTeX template — retries once on a compile
failure, and if it still won't compile returns the attempt (in the user's format) with
compiled=False + the error, instead of silently swapping to the generic build_tex layout."""

from __future__ import annotations

import pytest

from app.llm import client
from app.pipelines.apply import latex_regen, render

TEMPLATE = r"\documentclass{article}\begin{document}CUSTOM DESIGN\end{document}"
BAD = r"\documentclass{article}\begin{document}\undefinedcmd CUSTOM DESIGN\end{document}"


async def _regen(template_tex):
    return await latex_regen.regenerate_cv_latex(
        template_tex=template_tex,
        profile_dict={"skills": ["Go"], "experience": [], "summary": "I build backends"},
        owner_name="Hunter", job_title="Backend Engineer", jd_text="Go",
        ats_recs={}, priority_techs=[],
    )


@pytest.mark.asyncio
async def test_honors_template_retries_then_explains(monkeypatch):
    calls = {"n": 0}

    async def fake_complete(system, prompt, *, max_tokens, feature):
        calls["n"] += 1
        return BAD  # never compiles, even after the repair prompt

    async def fake_checked(tex, *, timeout=30.0):
        return None, "! Undefined control sequence \\undefinedcmd"

    # LLM live only for the regen feature (so tailoring stays deterministic + doesn't call the mock).
    monkeypatch.setattr(client, "is_live", lambda feature=None: feature == "ats_analyze")
    monkeypatch.setattr(client, "complete_text", fake_complete)
    monkeypatch.setattr(render, "render_pdf_checked", fake_checked)

    res = await _regen(TEMPLATE)
    assert res.compiled is False
    assert res.fell_back == "no_compile"
    assert res.stderr and "Undefined" in res.stderr
    # returns the attempt in the user's format, NOT the generic build_tex layout
    assert "CUSTOM DESIGN" in res.latex and "undefinedcmd" in res.latex
    assert calls["n"] == 2  # first attempt + one repair retry


@pytest.mark.asyncio
async def test_success_returns_compiled_in_template(monkeypatch):
    async def fake_complete(system, prompt, *, max_tokens, feature):
        return TEMPLATE

    async def fake_checked(tex, *, timeout=30.0):
        return b"%PDF ok", ""

    monkeypatch.setattr(client, "is_live", lambda feature=None: feature == "ats_analyze")
    monkeypatch.setattr(client, "complete_text", fake_complete)
    monkeypatch.setattr(render, "render_pdf_checked", fake_checked)

    res = await _regen(TEMPLATE)
    assert res.compiled is True and res.fell_back is None
    assert "CUSTOM DESIGN" in res.latex


@pytest.mark.asyncio
async def test_no_template_uses_builtin_layout():
    # fake mode (LLM not live) + no template → documented build_tex fallback, still compiles.
    res = await _regen(None)
    assert res.fell_back == "no_template" and res.compiled is True
    assert "documentclass" in res.latex.lower()

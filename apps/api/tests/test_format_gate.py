"""The deterministic ATS format gate over a rendered artifact."""

import shutil

import pytest

from app.api.onboarding import _template_gate
from app.core.errors import DomainError
from app.pipelines.apply import format_gate


def test_unevaluated_without_a_compiler():
    # No LaTeX engine → we cannot trust the artifact → unevaluated, never a fake pass.
    g = format_gate.evaluate(tex="\\documentclass{article}", pdf=b"stub", has_compiler=False)
    assert g["status"] == "unevaluated"


def test_fail_when_it_did_not_compile():
    g = format_gate.evaluate(tex="x", pdf=None, has_compiler=True)
    assert g["status"] == "fail"
    assert any("compile" in r for r in g["reasons"])


def test_pass_single_column_with_extractable_text(monkeypatch):
    monkeypatch.setattr(format_gate, "_pdf_text_len", lambda pdf: 1500)
    g = format_gate.evaluate(
        tex="\\documentclass{article}\\begin{document}Jane Doe\\end{document}",
        pdf=b"pdf", has_compiler=True,
    )
    assert g["status"] == "pass"
    assert g["flags"]["single_column"] and g["flags"]["text_extractable"]


def test_two_column_layout_fails(monkeypatch):
    monkeypatch.setattr(format_gate, "_pdf_text_len", lambda pdf: 1500)
    g = format_gate.evaluate(tex="\\documentclass[twocolumn]{article}", pdf=b"pdf",
                             has_compiler=True)
    assert g["status"] == "fail"
    assert any("column" in r for r in g["reasons"])


def test_tables_in_flow_fail(monkeypatch):
    monkeypatch.setattr(format_gate, "_pdf_text_len", lambda pdf: 1500)
    g = format_gate.evaluate(tex="\\begin{tabular}{ll}a & b\\end{tabular}", pdf=b"pdf",
                             has_compiler=True)
    assert g["status"] == "fail"
    assert g["flags"]["no_tables"] is False


def test_blank_or_stub_pdf_fails_on_text(monkeypatch):
    # A stub/image-only PDF extracts ~no text — exactly the "stored a stub, marked ready" bug.
    monkeypatch.setattr(format_gate, "_pdf_text_len", lambda pdf: 0)
    g = format_gate.evaluate(tex="\\documentclass{article}", pdf=b"%PDF-stub",
                             has_compiler=True)
    assert g["status"] == "fail"
    assert g["flags"]["text_extractable"] is False


# --- gate at template upload/save (app.api.onboarding._template_gate) ---

@pytest.mark.asyncio
async def test_template_gate_none_for_empty_source():
    assert await _template_gate("") is None
    assert await _template_gate(None) is None


@pytest.mark.asyncio
async def test_template_gate_rejects_unsafe_template():
    # A shell/IO primitive must never be stored — assert_safe raises before any compile.
    with pytest.raises(DomainError):
        await _template_gate(
            "\\documentclass{article}\\begin{document}\\write18{rm -rf /}\\end{document}"
        )


@pytest.mark.asyncio
async def test_template_gate_unevaluated_without_a_compiler(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)  # no LaTeX engine
    g = await _template_gate(
        "\\documentclass{article}\\begin{document}Jane Doe\\end{document}"
    )
    assert g is not None and g["status"] == "unevaluated"

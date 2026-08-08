"""Rendered-rule teeth — the checks that catch content dropped/garbled in rendering.

These can't be provoked through the fresh-build fixtures (the canonical template renders
every field as extractable text), so they're exercised directly on crafted rendered
contexts: a link/education entry missing from the extracted text, or two extractors
disagreeing. Deterministic, no compile.
"""

from app.cv_engine.rules import default_registry
from app.cv_engine.rules.base import Phase, RuleContext

_PASS_GATE = {
    "status": "pass",
    "flags": {
        "single_column": True, "no_tables": True, "no_graphics": True, "text_extractable": True,
    },
    "reasons": [],
}


def _ctx(cv_json: dict, extracted: str, *, extract_b: str | None = None) -> RuleContext:
    ctx = RuleContext(cv_json=cv_json, ledger=[], name="Ada Hunter")
    ctx.gate = _PASS_GATE
    ctx.pdf = b"%PDF-nonempty"
    ctx.extracted_text = extracted
    ctx.extract_a = extracted
    ctx.extract_b = extract_b if extract_b is not None else extracted
    return ctx


def _ids(ctx) -> set[str]:
    return {v.rule_id for v in default_registry().run(ctx, Phase.rendered)}


def test_links_survive_flags_a_dropped_link():
    cv = {"summary": "x", "links": {"github": "https://github.com/adahunter"}}
    ctx = _ctx(cv, "Ada Hunter\nSummary\nx")  # link absent from extracted text
    assert "rendered.links_survive" in _ids(ctx)


def test_links_survive_passes_when_the_link_extracts():
    cv = {"summary": "x", "links": {"github": "https://github.com/adahunter"}}
    ctx = _ctx(cv, "Ada Hunter Summary x github.com/adahunter")
    assert "rendered.links_survive" not in _ids(ctx)


def test_education_survive_flags_dropped_education():
    cv = {"summary": "x", "education": [{"degree": "BSc", "school": "Unilag"}]}
    ctx = _ctx(cv, "Ada Hunter\nSummary\nx")  # school absent
    assert "rendered.education_survive" in _ids(ctx)


def test_education_survive_passes_when_present():
    cv = {"summary": "x", "education": [{"degree": "BSc", "school": "Unilag"}]}
    ctx = _ctx(cv, "Ada Hunter Summary Education Unilag")
    assert "rendered.education_survive" not in _ids(ctx)


def test_dual_extract_disagreement_is_flagged():
    cv = {"summary": "x", "skills": ["Go"]}
    # The name surfaces in extractor A but not extractor B → they disagree.
    ctx = _ctx(cv, "Ada Hunter Summary Skills", extract_b="Summary Skills")
    assert "rendered.dual_extract_agreement" in _ids(ctx)


def test_dual_extract_agreement_when_both_read_the_same():
    cv = {"summary": "x", "skills": ["Go"]}
    ctx = _ctx(cv, "Ada Hunter Summary Skills")  # extract_b defaults equal
    assert "rendered.dual_extract_agreement" not in _ids(ctx)

"""Bucket 5 — Rendered rules (artifact-measured only).

These run ONLY on a real compiled PDF and the text re-extracted from it (the
artifact is the truth). The format-gate flags are reused verbatim from
`format_gate.evaluate`; the survival + dual-extractor rules are the new teeth
that catch content silently dropped or garbled in rendering.
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable

from app.cv_engine.rules.base import FixMode, Phase, Rule, RuleContext, Severity, Violation

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Lowercase + strip all whitespace — survives PDF line-wrapping/spacing."""
    return _WS.sub("", (text or "").lower())


def _link_core(link: str) -> str:
    """Distinctive part of a link/email: drop scheme + trailing slash."""
    s = re.sub(r"^https?://", "", str(link or "").strip(), flags=re.I).rstrip("/")
    return _norm(s)


def _page_count(pdf: bytes | None) -> int:
    if not pdf:
        return 0
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(pdf)).pages)
    except Exception:  # noqa: BLE001 — a malformed/stub PDF has no readable pages
        return 0


def _gate_flag(ctx: RuleContext, flag: str) -> bool | None:
    if not ctx.gate:
        return None
    return (ctx.gate.get("flags") or {}).get(flag)


def _compiles(ctx: RuleContext) -> Iterable[Violation]:
    if ctx.gate and ctx.gate.get("status") == "fail" and not (ctx.gate.get("flags")):
        # A hard compile failure (no flags computed) — the document did not compile.
        yield Violation(
            rule_id="rendered.compiles", severity=Severity.critical,
            message="The document did not compile to a PDF.",
            fix_hint="; ".join(ctx.gate.get("reasons") or ["compile failed"]),
        )


def _single_column(ctx: RuleContext) -> Iterable[Violation]:
    if _gate_flag(ctx, "single_column") is False:
        yield Violation(
            rule_id="rendered.single_column", severity=Severity.critical,
            message="Two-column layout — ATS parsers read across the columns.",
            fix_hint="Render single-column via the canonical template.",
        )


def _no_tables(ctx: RuleContext) -> Iterable[Violation]:
    if _gate_flag(ctx, "no_tables") is False:
        yield Violation(
            rule_id="rendered.no_tables", severity=Severity.major,
            message="Tables in the content flow break text-extraction order.",
            fix_hint="Replace tabular content with plain text / itemized lists.",
        )


def _no_graphics(ctx: RuleContext) -> Iterable[Violation]:
    if _gate_flag(ctx, "no_graphics") is False:
        yield Violation(
            rule_id="rendered.no_graphics", severity=Severity.major,
            message="Graphics/figures in the content flow confuse ATS parsers.",
            fix_hint="Remove images/figures from the content flow.",
        )


def _text_extractable(ctx: RuleContext) -> Iterable[Violation]:
    if _gate_flag(ctx, "text_extractable") is False:
        yield Violation(
            rule_id="rendered.text_extractable", severity=Severity.critical,
            message="Little or no text extracts from the rendered PDF.",
            fix_hint="Ensure the PDF embeds selectable text (not an image-only render).",
        )


def _page_limit(ctx: RuleContext) -> Iterable[Violation]:
    if not ctx.pdf:
        return
    limit = ctx.spec.page_limit if ctx.spec else 2  # the template's policy
    pages = _page_count(ctx.pdf)
    if pages > limit:
        yield Violation(
            rule_id="rendered.page_count", severity=Severity.minor,
            message=f"~{pages} pages — this template targets {limit}.",
            fix_hint=f"Trim the lowest-relevance content to fit {limit} page(s).",
        )


def _links_survive(ctx: RuleContext) -> Iterable[Violation]:
    if not ctx.extracted_text:  # nothing extracted (e.g. failed compile) — not this rule's call
        return
    hay = _norm(ctx.extracted_text)
    for key, val in (ctx.cv_json.get("links") or {}).items():
        core = _link_core(val)
        if core and core not in hay:
            yield Violation(
                rule_id="rendered.links_survive", severity=Severity.major,
                message=f"Contact link '{val}' did not survive rendering.",
                fix_hint="Ensure links render as selectable text; avoid unbreakable long URLs.",
                span={"where": "links", "key": key, "value": str(val)},
            )


def _education_survive(ctx: RuleContext) -> Iterable[Violation]:
    if not ctx.extracted_text:
        return
    hay = _norm(ctx.extracted_text)
    for ed in ctx.cv_json.get("education") or []:
        if isinstance(ed, str):
            anchor = ed
        else:
            anchor = ed.get("school") or ed.get("institution") or ed.get("degree") or ""
        anchor = str(anchor).strip()
        if anchor and _norm(anchor) not in hay:
            yield Violation(
                rule_id="rendered.education_survive", severity=Severity.major,
                message=f"Education entry '{anchor}' did not survive rendering.",
                fix_hint="Ensure the education section renders as extractable text.",
                span={"where": "education", "anchor": anchor},
            )


def _anchors(ctx: RuleContext) -> list[str]:
    """Distinctive strings that a faithful extractor must surface: the name, the
    canonical section headers the cv_json produces, and contact links."""
    out: list[str] = []
    if ctx.name:
        out.append(ctx.name)
    section_map = [
        ("summary", "Summary"), ("skills", "Skills"), ("experience", "Experience"),
        ("projects", "Projects"), ("education", "Education"),
        ("certifications", "Certifications"), ("languages", "Languages"),
    ]
    for key, header in section_map:
        if ctx.cv_json.get(key):
            out.append(header)
    for val in (ctx.cv_json.get("links") or {}).values():
        if str(val).strip():
            out.append(str(val))
    return out


def _dual_extract_agreement(ctx: RuleContext) -> Iterable[Violation]:
    if not ctx.extract_b:  # second extractor unavailable — nothing to compare
        return
    a, b = _norm(ctx.extract_a or ctx.extracted_text), _norm(ctx.extract_b)
    disagreements: list[str] = []
    for anchor in _anchors(ctx):
        needle = _link_core(anchor) if anchor.lower().startswith("http") else _norm(anchor)
        if not needle:
            continue
        if (needle in a) != (needle in b):
            disagreements.append(anchor)
    if disagreements:
        yield Violation(
            rule_id="rendered.dual_extract_agreement", severity=Severity.major,
            message="Two PDF extractors disagree on: " + ", ".join(disagreements[:6]),
            fix_hint="ATS parsers may read this differently — simplify the flagged content.",
            span={"disagreements": disagreements},
        )


RULES: list[Rule] = [
    Rule(id="rendered.compiles", severity=Severity.critical, phase=Phase.rendered,
         fix_mode=FixMode.deterministic, weight=5.0, check=_compiles,
         fix_hint="Fix the LaTeX so it compiles."),
    Rule(id="rendered.single_column", severity=Severity.critical, phase=Phase.rendered,
         fix_mode=FixMode.na, weight=5.0, check=_single_column,
         fix_hint="Render single-column via the canonical template."),
    Rule(id="rendered.no_tables", severity=Severity.major, phase=Phase.rendered,
         fix_mode=FixMode.na, weight=3.0, check=_no_tables,
         fix_hint="Replace tables with plain text."),
    Rule(id="rendered.no_graphics", severity=Severity.major, phase=Phase.rendered,
         fix_mode=FixMode.na, weight=3.0, check=_no_graphics,
         fix_hint="Remove graphics from the content flow."),
    Rule(id="rendered.text_extractable", severity=Severity.critical, phase=Phase.rendered,
         fix_mode=FixMode.deterministic, weight=5.0, check=_text_extractable,
         fix_hint="Embed selectable text."),
    Rule(id="rendered.page_count", severity=Severity.minor, phase=Phase.rendered,
         fix_mode=FixMode.agent, weight=0.5, check=_page_limit,
         fix_hint="Trim to two pages."),
    Rule(id="rendered.links_survive", severity=Severity.major, phase=Phase.rendered,
         fix_mode=FixMode.deterministic, weight=2.0, check=_links_survive,
         fix_hint="Ensure links render as selectable text."),
    Rule(id="rendered.education_survive", severity=Severity.major, phase=Phase.rendered,
         fix_mode=FixMode.deterministic, weight=2.0, check=_education_survive,
         fix_hint="Ensure education renders as extractable text."),
    Rule(id="rendered.dual_extract_agreement", severity=Severity.major, phase=Phase.rendered,
         fix_mode=FixMode.deterministic, weight=2.0, check=_dual_extract_agreement,
         fix_hint="Simplify layout/encoding so both extractors agree."),
]

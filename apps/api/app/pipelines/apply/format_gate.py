"""The ATS format gate — structural parseability of a *rendered* artifact.

Deterministic, no model call (so it keeps working when the AI layer is offline). It
answers one pass/fail question: would an ATS parser read this document correctly?

- `.tex` signals: multi-column layout and tables/graphics in the content flow are the
  classic ATS killers (parsers read across columns, and tables scramble text order).
- PDF signal: whether text actually extracts (an image-only or blank/stub PDF yields
  nothing — which is exactly the "stored a stub, marked it ready" trust bug).

Crucially, absence of a measurement is NEVER encoded as a pass: when no real artifact
was produced (no compiler available), the gate is `unevaluated`, not `pass`.
"""

from __future__ import annotations

import io
import re

_MIN_TEXT_CHARS = 200  # a real one-page CV extracts far more; a stub/blank extracts ~0

_TWO_COLUMN = re.compile(
    r"\\begin\{multicols\}|\\twocolumn\b|\\columnbreak\b|\\begin\{paracol\}"
    r"|\\documentclass\[[^\]]*\btwocolumn\b",
)
_TABLE = re.compile(r"\\begin\{(tabular|tabularx|longtable|table)\b")
_GRAPHIC = re.compile(r"\\includegraphics\b|\\begin\{tikzpicture\}|\\begin\{figure\}")


def _pdf_text_len(pdf: bytes | None) -> int:
    if not pdf:
        return 0
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf))
        return sum(len((page.extract_text() or "")) for page in reader.pages)
    except Exception:  # noqa: BLE001 — a malformed/stub PDF extracts nothing
        return 0


def evaluate(*, tex: str | None, pdf: bytes | None, has_compiler: bool = True) -> dict:
    """Return the gate: {status: pass|fail|unevaluated, flags, reasons, text_chars}.

    `pdf` should be the *real* compiled artifact, or None if it didn't compile. Pass
    `has_compiler=False` when no LaTeX engine was available — the artifact cannot be
    trusted, so the gate is `unevaluated` (never a fabricated pass).
    """
    if not has_compiler:
        return {"status": "unevaluated", "flags": {}, "reasons": [], "text_chars": 0}
    if pdf is None:
        return {"status": "fail", "flags": {}, "reasons": ["the document did not compile"],
                "text_chars": 0}

    t = tex or ""
    two_col = bool(_TWO_COLUMN.search(t))
    has_table = bool(_TABLE.search(t))
    has_graphic = bool(_GRAPHIC.search(t))
    text_chars = _pdf_text_len(pdf)
    extractable = text_chars >= _MIN_TEXT_CHARS

    flags = {
        "single_column": not two_col,
        "no_tables": not has_table,
        "no_graphics": not has_graphic,
        "text_extractable": extractable,
    }
    reasons: list[str] = []
    if two_col:
        reasons.append("two-column layout — ATS parsers read across the columns")
    if has_table:
        reasons.append("tables in the content flow break text-extraction order")
    if has_graphic:
        reasons.append("graphics/figures in the content flow")
    if not extractable:
        reasons.append("little or no text extracts from the rendered PDF")

    return {
        "status": "pass" if not reasons else "fail",
        "flags": flags,
        "reasons": reasons,
        "text_chars": text_chars,
    }

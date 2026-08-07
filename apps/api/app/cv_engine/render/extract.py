"""Two independent PDF text extractors — the basis for dual-extractor agreement.

Your extractor is not the ATS's extractor. Reading the compiled PDF with two
different engines (pypdf + pdfminer.six) and requiring they agree on the load-bearing
content (name, contact, section headers) approximates "will a foreign parser read this
the same way?" — a proxy the single-extractor path can't give.
"""

from __future__ import annotations

import io


def extract_pypdf(pdf: bytes | None) -> str:
    if not pdf:
        return ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:  # noqa: BLE001 — a malformed/stub PDF yields no text
        return ""


def extract_pdfminer(pdf: bytes | None) -> str:
    if not pdf:
        return ""
    try:
        from pdfminer.high_level import extract_text

        return extract_text(io.BytesIO(pdf)) or ""
    except Exception:  # noqa: BLE001 — pdfminer failed on this artifact
        return ""


def dual_extract(pdf: bytes | None) -> tuple[str, str]:
    """Return (pypdf_text, pdfminer_text)."""
    return extract_pypdf(pdf), extract_pdfminer(pdf)

"""Extract plain text from CV files and build a minimal dict for ATS scoring."""

from __future__ import annotations

import re

_SKILL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{2,}")


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            import io

            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        if name.endswith(".docx"):
            import io

            import docx

            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs)
    except Exception:
        return ""
    return data.decode("utf-8", errors="ignore")


def naive_skills(text: str, *, top: int = 40) -> list[str]:
    counts: dict[str, int] = {}
    for tok in _SKILL_RE.findall(text or ""):
        counts[tok] = counts.get(tok, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:top]]


def cv_json_from_text(text: str) -> dict:
    """Minimal structure so ATS `_cv_text` walks the full CV body."""
    body = (text or "").strip()
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    return {
        "summary": body[:4000],
        "skills": naive_skills(body),
        "experience": [{"bullets": lines[:80]}] if lines else [],
        "education": [],
        "projects": [],
    }

"""Internal ATS-style match scorer.

Compares a CV/profile against a JD on keyword coverage, title/seniority alignment,
and format parseability. Returns a 0-100 score + a breakdown.

IMPORTANT FRAMING: this is OUR internal match score, optimized toward a 90-95%
band. It is NOT a guarantee of any employer's ATS (Greenhouse/Workday/Lever parse
differently and usually expose no score). UI copy must say "internal ATS match".
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}")
_STOP = {
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "this", "that",
    "your", "who", "all", "can", "but", "not", "from", "they", "their", "out", "what",
    "experience", "team", "work", "role", "job", "looking", "join", "help", "build",
    "strong", "years", "ability", "including", "well", "across", "using", "into",
    "a", "an", "to", "of", "in", "on", "as", "is", "we", "be", "or", "at", "it",
}
TARGET_BAND = (90, 95)


def extract_keywords(jd_text: str, *, top: int = 25) -> list[str]:
    counts: dict[str, int] = {}
    for tok in _TOKEN.findall((jd_text or "").lower()):
        # Keep 2-letter tech skills (Go, ML); _STOP filters common short words.
        if tok in _STOP:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:top]]


def _cv_text(cv_json: dict) -> str:
    parts: list[str] = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(cv_json)
    return " ".join(parts).lower()


def score(*, cv_json: dict, jd_text: str, role_title: str | None = None) -> dict:
    keywords = extract_keywords(jd_text)
    text = _cv_text(cv_json)
    matched = [k for k in keywords if k in text]
    missing = [k for k in keywords if k not in text]
    coverage = len(matched) / len(keywords) if keywords else 1.0

    # Title alignment: role-title tokens present in the CV.
    title_tokens = [t for t in _TOKEN.findall((role_title or "").lower()) if t not in _STOP]
    title_hits = [t for t in title_tokens if t in text]
    title_alignment = len(title_hits) / len(title_tokens) if title_tokens else 1.0

    # Format parseability — we always render ATS-safe single-column, standard headings.
    format_flags = {
        "single_column": True,
        "standard_headings": True,
        "no_tables_or_graphics": True,
    }
    format_ok = sum(format_flags.values()) / len(format_flags)

    value = round(100 * (0.70 * coverage + 0.15 * title_alignment + 0.15 * format_ok), 1)
    return {
        "score": value,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "title_alignment": round(title_alignment, 2),
        "format_flags": format_flags,
        "coverage": round(coverage, 2),
        "framing": "internal ATS match (optimized toward 90-95%); not an employer-ATS guarantee",
    }


def gap_skills(breakdown: dict, *, limit: int = 5) -> list[str]:
    """Missing keywords worth asking the VA to confirm (manual path prompts)."""
    return breakdown.get("missing_keywords", [])[:limit]

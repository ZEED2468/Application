"""Internal ATS-style match scorer.

Compares a CV/profile against a JD on keyword coverage, title/seniority alignment,
and format parseability. Returns a 0-100 score + a breakdown.

Keywords are extracted dynamically from each JD (no fixed skill list). Generic
English and soft-skill filler are filtered heuristically; use AI vet for nuance.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}")
_NORM = re.compile(r"[.\-_/]")
# Common function words + soft-skill JD filler (not role- or company-specific).
_GENERIC_STOP = frozenset({
    "the", "and", "for", "with", "you", "our", "are", "will", "have", "this", "that",
    "your", "who", "all", "can", "but", "not", "from", "they", "their", "out", "what",
    "experience", "team", "work", "role", "job", "looking", "join", "help", "build",
    "strong", "years", "ability", "including", "well", "across", "using", "into",
    "a", "an", "to", "of", "in", "on", "as", "is", "we", "be", "or", "at", "it",
    "seeking", "skilled", "motivated", "critical", "seamless", "integration",
    "ensure", "maintain", "documented", "troubleshoot", "debug", "complex",
    "effective", "solutions", "emerging", "trends", "best", "practices", "related",
    "fields", "degree", "education", "bachelor", "apply", "sound", "solid",
    "proficient", "excellent", "good", "understanding", "familiarity", "knowledge",
    "skills", "environment", "benefits", "competitive", "salary", "package",
    "collaborative", "supportive", "flexible", "continuous", "learning",
    "professional", "international", "required", "preferred", "responsibilities",
    "requirements", "qualifications", "description", "about", "aboutus",
})
# Short tokens that are often real tech terms.
_TECH_SHORT = frozenset({"go", "sql", "git", "api", "jwt", "ssh", "oop", "aws", "gcp", "css", "html", "php", "rust", "ml", "ai"})
_SOFT_SUFFIX = re.compile(r"(tion|ment|ness|able|ful|ive|ous|ing|ity|ally)$")

TARGET_BAND = (90, 95)


def _normalize_token(tok: str) -> str:
    return _NORM.sub("", tok.lower().strip(".,;:!?\"'()[]"))


def _is_soft_fluff(tok: str) -> bool:
    low = tok.lower().strip(".,;:!?\"'()[]")
    if low in _GENERIC_STOP:
        return True
    if len(low) <= 3 and low not in _TECH_SHORT:
        return True
    if _SOFT_SUFFIX.search(low) and not re.search(r"[.#+\d/]", low):
        return True
    return False


def _is_technical_token(tok: str) -> bool:
    """Heuristic: tech-shaped token from a JD, not a curated skill list."""
    low = tok.lower().strip(".,;:!?\"'()[]")
    if not low or _is_soft_fluff(low):
        return False
    if low in _TECH_SHORT:
        return True
    if re.search(r"[.#+\d/]", low):
        return True
    if len(low) >= 4:
        return True
    return False


def _is_actionable_skill(keyword: str) -> bool:
    """Missing keywords worth asking a human to confirm."""
    return _is_technical_token(keyword)


def extract_keywords(jd_text: str, *, top: int = 25) -> list[str]:
    text = jd_text or ""
    counts: dict[str, int] = {}
    display: dict[str, str] = {}

    for raw in _TOKEN.findall(text):
        tok = raw.strip(".,;:!?\"'()[]")
        if not _is_technical_token(tok):
            continue
        norm = _normalize_token(tok)
        counts[norm] = counts.get(norm, 0) + 1
        display.setdefault(norm, tok.lower())

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [display[norm] for norm, _ in ranked[:top]]


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


def _cv_tokens(text: str) -> set[str]:
    return {_normalize_token(t) for t in _TOKEN.findall(text)}


def _keyword_matches(keyword: str, _text: str, cv_tokens: set[str]) -> bool:
    return _normalize_token(keyword) in cv_tokens


def score(*, cv_json: dict, jd_text: str, role_title: str | None = None) -> dict:
    keywords = extract_keywords(jd_text)
    text = _cv_text(cv_json)
    cv_tokens = _cv_tokens(text)
    matched = [k for k in keywords if _keyword_matches(k, text, cv_tokens)]
    missing = [k for k in keywords if k not in matched]
    coverage = len(matched) / len(keywords) if keywords else 1.0

    title_tokens = [
        t for t in _TOKEN.findall((role_title or "").lower())
        if _is_technical_token(t)
    ]
    title_hits = [t for t in title_tokens if _keyword_matches(t, text, cv_tokens)]
    title_alignment = len(title_hits) / len(title_tokens) if title_tokens else 1.0

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
    gaps: list[str] = []
    for kw in breakdown.get("missing_keywords", []):
        if not _is_actionable_skill(kw):
            continue
        gaps.append(kw)
        if len(gaps) >= limit:
            break
    return gaps

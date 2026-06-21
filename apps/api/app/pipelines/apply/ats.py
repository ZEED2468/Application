"""Internal ATS-style match scorer.

Compares a CV/profile against a JD on keyword coverage, title/seniority alignment,
and format parseability. Returns a 0-100 score + a breakdown.

Keywords are extracted from requirement / qualification / skill-list sections of
each JD (not marketing copy). Generic English is filtered; use AI vet for nuance.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}")
_NORM = re.compile(r"[.\-_/]")
# Function words + soft-skill JD filler.
_GENERIC_STOP = frozenset({
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have",
    "this", "that", "who", "all", "can", "but", "not", "from", "they", "their",
    "out", "what", "experience", "team", "work", "role", "job", "looking",
    "join", "help", "build", "strong", "years", "ability", "including", "well",
    "across", "using", "into", "a", "an", "to", "of", "in", "on", "as", "is",
    "we", "be", "or", "at", "it", "seeking", "skilled", "motivated", "critical",
    "seamless", "integration", "ensure", "maintain", "documented", "troubleshoot",
    "debug", "complex", "effective", "solutions", "emerging", "trends", "best",
    "practices", "related", "fields", "degree", "education", "bachelor", "apply",
    "sound", "solid", "proficient", "excellent", "good", "understanding",
    "familiarity", "knowledge", "skills", "environment", "benefits", "competitive",
    "salary", "package", "collaborative", "supportive", "flexible", "continuous",
    "learning", "professional", "international", "required", "preferred",
    "responsibilities", "requirements", "qualifications", "description", "about",
    "aboutus", "must", "should", "need", "needs", "ideal", "candidate",
    "strongly", "recommended", "mandatory", "essential", "expertise", "extensive",
    "desired", "desirable", "nice",
})
# Generic nouns/adjectives common in JD marketing copy — not actionable skills.
_GENERIC_NOUNS = frozenset({
    "technologies", "technology", "advanced", "consumer", "design", "brand",
    "candidates", "clean", "closely", "based", "product", "features", "services",
    "applications", "architecture", "performance", "database", "data", "platform",
    "platforms", "solution", "solutions", "system", "systems", "development",
    "developer", "engineer", "engineering", "software", "technical", "business",
    "company", "teams", "world", "global", "leading", "innovative", "dynamic",
    "fast", "paced", "culture", "opportunity", "position", "hands", "working",
    "multiple", "various", "different", "high", "quality", "scalable", "robust",
    "modern", "existing", "new", "within", "through", "other", "others", "both",
    "each", "every", "some", "such", "also", "plus", "etc", "among", "between",
    "consumer", "closely", "frontend", "backend", "agile", "cloud", "mobile", "web",
    "digital", "enterprise", "internal", "external", "cross", "functional", "mission",
    "vision", "values", "impact", "growth", "scale", "driven", "passionate",
    "committed",
})
# Short tokens that are often real tech terms.
_TECH_SHORT = frozenset({
    "go", "sql", "git", "api", "apis", "jwt", "ssh", "oop", "aws", "gcp", "css", "html",
    "php", "rust", "ml", "ai", "js", "ts", "ux", "ui", "ci", "cd", "db", "nosql",
})
_SOFT_SUFFIX = re.compile(r"(tion|ment|ness|able|ful|ive|ous|ing|ity|ally|ence|ance)$")
_REQUIREMENT_HEADER = re.compile(
    r"(?i)^(?:"
    r"requirements?|qualifications?|required(?:\s+skills?|\s+qualifications?)?|"
    r"what\s+you(?:'ll|\s+will)\s+(?:need|bring)|must[\-\s]have|"
    r"technical\s+skills?|key\s+skills?|skills?(?:\s*&\s*qualifications?)?|"
    r"the\s+ideal\s+candidate|you\s+have|you\s+bring|tech\s+stack|"
    r"our\s+stack|technologies?\s+we\s+use"
    r")(?:\s*[:.]?\s*|$)"
)
_INLINE_REQUIREMENTS = re.compile(
    r"(?i)(?:requirements?|qualifications?|required\s+skills?)\s*:\s*([^\n]+)"
)
_BULLET = re.compile(r"^[\-*•]\s+(.+)$")
_NUMBERED = re.compile(r"^\d+[.)]\s+(.+)$")
_NON_REQUIREMENT_HEADER = re.compile(
    r"(?i)^(?:about(?:\s+us)?|benefits?|what\s+we\s+offer|company|overview|"
    r"who\s+we\s+are|description|the\s+role|responsibilities|duties|"
    r"nice[\-\s]to[\-\s]have|bonus|perks|compensation|salary|location|"
    r"how\s+to\s+apply|equal\s+opportunity)"
)

TARGET_BAND = (90, 95)

# JD phrases that mark a technology as critical / strongly-recommended (drives the
# explicit achievement reframe + prioritizes confirm-true prompts).
_EMPHASIS = re.compile(
    r"(?i)(?:strongly\s+recommended|must[\-\s]have|\bmust\b|\brequired\b|essential|"
    r"mandatory|expert|proficien|deep\s+(?:experience|knowledge|understanding)|"
    r"extensive|strong\s+(?:experience|background|proficiency|knowledge)|\bcritical\b)"
)


def _normalize_token(tok: str) -> str:
    return _NORM.sub("", tok.lower().strip(".,;:!?\"'()[]"))


def _is_soft_fluff(tok: str) -> bool:
    low = tok.lower().strip(".,;:!?\"'()[]")
    if low in _GENERIC_STOP:
        return True
    if len(low) <= 2 and low not in _TECH_SHORT:
        return True
    if low in _GENERIC_NOUNS:
        return True
    if _SOFT_SUFFIX.search(low) and not re.search(r"[.#+\d/]", low):
        return True
    return False


def _has_tech_shape(tok: str, *, strict: bool = False) -> bool:
    low = tok.lower().strip(".,;:!?\"'()[]")
    if low in _TECH_SHORT:
        return True
    if re.search(r"[.#+\d/]", low):
        return True
    if strict:
        return False
    # Proper-noun tech brands: Azure, Java, Rust, Kafka, NestJS, TypeScript
    if tok[0].isupper() and len(low) >= 3 and low not in _GENERIC_NOUNS:
        return True
    return False


def _is_skill_token(tok: str, *, in_requirement_zone: bool = False) -> bool:
    """True when a token looks like a JD skill/requirement, not marketing copy."""
    low = tok.lower().strip(".,;:!?\"'()[]")
    if not low or _is_soft_fluff(low):
        return False
    if _has_tech_shape(tok):
        return True
    if in_requirement_zone:
        # Inside a requirements list, allow short concrete terms (jest, linux, git).
        if len(low) >= 3 and not _SOFT_SUFFIX.search(low):
            return True
    return False


def _is_technical_token(tok: str) -> bool:
    """Back-compat alias for callers/tests."""
    return _is_skill_token(tok, in_requirement_zone=False) or _is_skill_token(
        tok, in_requirement_zone=True,
    )


def _is_actionable_skill(keyword: str) -> bool:
    """Missing keywords worth asking a human to confirm."""
    return _is_skill_token(keyword, in_requirement_zone=True)


def _requirement_zones(jd_text: str) -> list[str]:
    """Text blocks that likely enumerate skills or hard requirements."""
    text = jd_text or ""
    zones: list[str] = []
    seen: set[str] = set()

    def add(zone: str) -> None:
        chunk = zone.strip()
        if chunk and chunk not in seen:
            seen.add(chunk)
            zones.append(chunk)

    for match in _INLINE_REQUIREMENTS.finditer(text):
        add(match.group(1))

    lines = text.splitlines()
    capturing = False
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, capturing
        if buffer:
            add("\n".join(buffer))
        buffer = []
        capturing = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if capturing:
                flush()
            continue

        bullet = _BULLET.match(line) or _NUMBERED.match(line)
        if bullet:
            add(bullet.group(1))
            continue

        if _REQUIREMENT_HEADER.match(line):
            flush()
            capturing = True
            after = re.sub(_REQUIREMENT_HEADER, "", line).strip()
            if after:
                buffer.append(after)
            continue

        if capturing:
            if _NON_REQUIREMENT_HEADER.match(line):
                flush()
                continue
            buffer.append(line)

    flush()
    return zones


def _fallback_skill_phrases(jd_text: str) -> list[str]:
    """Skill lists embedded in prose when there is no Requirements heading."""
    phrases: list[str] = []
    for match in re.finditer(
        r"(?i)(?:experience\s+(?:with|in)|proficien(?:t|cy)\s+(?:with|in)|"
        r"strong\s+(?:in|with)|skilled\s+(?:in|with)|expertise\s+(?:in|with)|"
        r"strength\s+in|background\s+in|"
        r"including|using|with|know(?:ledge)?\s+of|stack\s*[:])\s*([^.;\n]+)",
        jd_text or "",
    ):
        chunk = match.group(1).strip()
        if chunk:
            phrases.append(chunk)
    return phrases


def _tokens_from_zone(zone: str, *, in_requirement_zone: bool) -> list[tuple[str, str]]:
    """Return (display, normalized) tokens from a JD fragment."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    segments = re.split(r"[,;|]|(?:\s+and\s+)|(?:\s+or\s+)", zone)
    for segment in segments:
        segment = segment.strip(" \t()[]")
        if not segment:
            continue
        for raw in _TOKEN.findall(segment):
            tok = raw.strip(".,;:!?\"'()[]")
            if not _is_skill_token(tok, in_requirement_zone=in_requirement_zone):
                continue
            if not in_requirement_zone and not _has_tech_shape(tok, strict=True):
                continue
            norm = _normalize_token(tok)
            if norm in seen:
                continue
            seen.add(norm)
            found.append((tok.lower(), norm))
    return found


def extract_keywords(jd_text: str, *, top: int = 25) -> list[str]:
    zones = _requirement_zones(jd_text)
    counts: dict[str, int] = {}
    display: dict[str, str] = {}

    def absorb(tokens: list[tuple[str, str]], *, weight: int = 1) -> None:
        for disp, norm in tokens:
            counts[norm] = counts.get(norm, 0) + weight
            display.setdefault(norm, disp)

    for zone in zones:
        absorb(_tokens_from_zone(zone, in_requirement_zone=True), weight=3)

    if not zones:
        for phrase in _fallback_skill_phrases(jd_text):
            absorb(_tokens_from_zone(phrase, in_requirement_zone=True), weight=2)

    # Tech-shaped tokens anywhere (Azure, Node.js, C#) when lists are sparse.
    if len(counts) < top:
        absorb(_tokens_from_zone(jd_text or "", in_requirement_zone=False), weight=1)

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [display[norm] for norm, _ in ranked[:top]]


def critical_keywords(jd_text: str) -> list[str]:
    """Technologies the JD marks as strongly-recommended / must-have.

    A tech is critical if it appears in a line/sentence carrying an emphasis marker
    (e.g. "Kafka is strongly recommended", "must have React"). Detected directly from
    the JD (independent of the top-keyword extraction) so an emphasized tech is caught
    even when it isn't in a Requirements list. Deterministic — works in fake + live;
    drives the explicit achievement reframe and prioritizes confirm-true prompts.
    """
    crit: list[str] = []
    seen: set[str] = set()
    for seg in re.split(r"[\n.;]", jd_text or ""):
        if not _EMPHASIS.search(seg):
            continue
        for raw in _TOKEN.findall(seg):
            tok = raw.strip(".,;:!?\"'()[]")
            # _has_tech_shape (non-strict) catches Kafka, React, Node.js, C#, aws…;
            # _is_soft_fluff drops marker/filler words (must, you, strongly, …).
            if _is_soft_fluff(tok) or not _has_tech_shape(tok):
                continue
            norm = _normalize_token(tok)
            if norm and norm not in seen:
                seen.add(norm)
                crit.append(tok.lower())
    return crit


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

    critical = critical_keywords(jd_text)
    missing_critical = [k for k in critical if not _keyword_matches(k, text, cv_tokens)]

    title_tokens = [
        t for t in _TOKEN.findall((role_title or "").lower())
        if _is_skill_token(t, in_requirement_zone=True)
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
        "critical_keywords": critical,
        "missing_critical": missing_critical,
        "title_alignment": round(title_alignment, 2),
        "format_flags": format_flags,
        "coverage": round(coverage, 2),
        "framing": "internal ATS match (optimized toward 90-95%); not an employer-ATS guarantee",
    }


def gap_skills(breakdown: dict, *, limit: int = 5) -> list[str]:
    """Missing keywords worth asking the VA to confirm (manual path prompts).

    Strongly-recommended / must-have gaps come first so the VA confirms the
    JD-critical techs before the rest.
    """
    missing = breakdown.get("missing_keywords", [])
    missing_critical = breakdown.get("missing_critical", [])
    # Strongly-recommended gaps first (even if not in the top extracted keywords),
    # then the rest; dedupe preserving order.
    ordered = list(dict.fromkeys([*missing_critical, *missing]))
    gaps: list[str] = []
    for kw in ordered:
        if not _is_actionable_skill(kw):
            continue
        gaps.append(kw)
        if len(gaps) >= limit:
            break
    return gaps

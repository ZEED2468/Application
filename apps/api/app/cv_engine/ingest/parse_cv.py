"""Deterministic CV parser — 'honest 80%' text → structured cv_json.

Text-based, single-column, zero-LLM. It records what it can read and flags what it
can't (per-section confidence + flags) rather than guessing; a scanned/image-only PDF
(≈ no extractable text) is gated with a clean 'can't read this yet', and non-CV text is
flagged. Section headers are canonicalized (canonical.match_header) and dates normalized
(fixes.normalize_date_string), so the output already matches the render/ledger shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.cv_engine.fixes.deterministic import tidy_value
from app.cv_engine.ingest.canonical import CANONICAL_ORDER, match_header
from app.cv_engine.ingest.normalize import normalize_text
from app.pipelines.apply.format_gate import _MIN_TEXT_CHARS
from app.pipelines.apply.intel import _EMAIL, _PHONE

_BULLET = re.compile(r"^\s*[-•*–‣·▪◦]\s+")
_SPLIT_SKILLS = re.compile(r"[,\n•|/·;]|\s+-\s+|\s{2,}")
_TITLE_SEP = re.compile(r"\s+[—–\-|]\s+|\s+at\s+|,\s+", re.I)
# A date range or single year token embedded anywhere in a header line.
_MONTH = r"(?:[A-Za-z]{3,9}\.?\s+)?"
_DATEPART = rf"(?:{_MONTH}\d{{4}}|\d{{1,2}}[/-]\d{{4}})"
_PRESENT = r"(?:present|current|now|ongoing|to date)"
_DATE_RANGE = re.compile(
    rf"({_DATEPART})\s*(?:[-–—]|to|–|—)\s*({_DATEPART}|{_PRESENT})", re.I
)


@dataclass
class ParsedCv:
    cv_json: dict = field(default_factory=dict)
    confidence: dict = field(default_factory=dict)
    flags: list = field(default_factory=list)
    is_cv: bool = False
    scanned: bool = False
    structured_by: str = "deterministic"


def _find_dates(line: str) -> tuple[str | None, str]:
    """Extract a date range from a line; return (raw_dates|None, line_without_dates).

    Dates are recorded RAW (ingest records, never judges) — the PATCH phase normalizes them
    to the canonical ' -- ' form, so the revamp delta shows exactly what got fixed."""
    m = _DATE_RANGE.search(line)
    if not m:
        return None, line
    raw = m.group(0).strip()
    rest = (line[: m.start()] + " " + line[m.end():]).strip(" -–—|,·\t")
    return raw, rest


def _links(text: str) -> dict:
    low = text.lower()
    links: dict[str, str] = {}
    em = _EMAIL.search(text)
    if em:
        links["email"] = em.group(0)
    ph = _PHONE.search(text)
    if ph:
        links["phone"] = ph.group(0).strip()
    for host, key in (("linkedin.com", "linkedin"), ("github.com", "github")):
        m = re.search(rf"[\w./:-]*{re.escape(host)}[\w./#-]*", low)
        if m:
            links[key] = m.group(0)
    return links


def _split_sections(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Return (preamble_lines_before_first_header, {canonical_key: [lines]})."""
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        key = match_header(line)
        if key:
            current = key
            sections.setdefault(key, [])
            continue
        if current is None:
            preamble.append(line)
        else:
            sections[current].append(line)
    return preamble, sections


def _parse_entry(header_lines: list[str], bullets: list[str]) -> dict:
    dates: str | None = None
    cleaned: list[str] = []
    for hl in header_lines:
        d, rest = _find_dates(hl)
        if d and not dates:
            dates = d
        rest = rest.strip(" -–—|,·")
        if rest:
            cleaned.append(rest)
    title = company = None
    if cleaned:
        parts = _TITLE_SEP.split(cleaned[0], maxsplit=1)
        if len(parts) == 2:
            title, company = parts[0].strip(), parts[1].strip()
        elif len(cleaned) >= 2:
            title, company = cleaned[0], cleaned[1]
        else:
            title = cleaned[0]
    entry: dict = {"bullets": bullets}
    if title:
        entry["title"] = title
    if company:
        entry["company"] = company
    if dates:
        entry["dates"] = dates
    return entry


def _parse_entries(lines: list[str]) -> list[dict]:
    """Segment section lines into entries: [header lines…][bullets…], repeating."""
    entries: list[dict] = []
    header: list[str] = []
    bullets: list[str] = []
    prev_bullet = False

    def _flush() -> None:
        if header or bullets:
            entries.append(_parse_entry(header, bullets))

    for line in lines:
        if not line.strip():
            continue
        if _BULLET.match(line):
            bullets.append(_BULLET.sub("", line).strip())
            prev_bullet = True
        else:
            if prev_bullet:  # a non-bullet after bullets opens a new entry
                _flush()
                header, bullets = [], []
            header.append(line.strip())
            prev_bullet = False
    _flush()
    return [e for e in entries if e.get("title") or e.get("company") or e.get("bullets")]


def _parse_education(entries: list[dict]) -> list[dict]:
    out: list[dict] = []
    for e in entries:
        row: dict = {}
        # reuse experience segmentation; map title→degree, company→school
        if e.get("title"):
            row["degree"] = e["title"]
        if e.get("company"):
            row["school"] = e["company"]
        if e.get("dates"):
            row["dates"] = e["dates"]
        # loose bullets become extra detail lines
        extra = " ".join(e.get("bullets") or [])
        if not row and extra:
            row["degree"] = extra
        if row:
            out.append(row)
    return out


def _parse_skills(section_lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in _SPLIT_SKILLS.split(" \n ".join(section_lines)):
        tok = tidy_value(raw).strip(" :–-—•*·")
        if 1 <= len(tok) <= 40 and not tok.endswith(".") and not match_header(tok):
            out.append(tok)
    return list(dict.fromkeys(out))


def parse_cv_text(text: str) -> ParsedCv:
    norm = normalize_text(text)
    if len(norm) < _MIN_TEXT_CHARS:
        # ≈ no extractable text — image-only / scanned (no OCR exists).
        return ParsedCv(flags=["scanned"], is_cv=False, scanned=True)

    lines = norm.split("\n")
    preamble, sections = _split_sections(lines)
    links = _links(norm)

    cv: dict = {}
    if links:
        cv["links"] = links
    # Preamble is usually [Name, Title/headline, contact…]. The name belongs on the User
    # record, not the cv_json, so the headline is the SECOND non-contact line (the role).
    noncontact = [
        s.strip() for s in preamble
        if s.strip() and "@" not in s and not _PHONE.search(s)
    ]
    if len(noncontact) >= 2 and 3 <= len(noncontact[1]) <= 60:
        cv["headline"] = noncontact[1]

    if "summary" in sections:
        cv["summary"] = tidy_value(" ".join(sections["summary"]))
    if "skills" in sections:
        cv["skills"] = _parse_skills(sections["skills"])
    if "experience" in sections:
        cv["experience"] = _parse_entries(sections["experience"])
    if "projects" in sections:
        cv["projects"] = [
            {"name": e.get("title") or (e.get("bullets") or [""])[0],
             "description": " ".join(e.get("bullets") or [])}
            for e in _parse_entries(sections["projects"])
        ]
    if "education" in sections:
        cv["education"] = _parse_education(_parse_entries(sections["education"]))
    for key in ("certifications", "languages"):
        if key in sections:
            cv[key] = [tidy_value(x) for x in sections[key] if tidy_value(x)]

    # --- confidence + honesty flags ---
    flags: list[str] = []
    conf: dict[str, float] = {}
    heading_count = len(sections)
    has_contact = bool(links.get("email") or links.get("phone"))
    is_cv = heading_count >= 2 or (has_contact and heading_count >= 1)
    if not is_cv:
        flags.append("not_a_cv")
    if not has_contact:
        flags.append("no_contact")

    exp = cv.get("experience") or []
    if exp:
        dated = sum(1 for e in exp if e.get("dates") and (e.get("title") or e.get("company")))
        conf["experience"] = round(dated / len(exp), 2)
        if conf["experience"] < 0.5:
            flags.append("low_confidence:experience")
        if not any(e.get("dates") for e in exp):
            flags.append("no_dates")
    elif "experience" in sections:
        conf["experience"] = 0.0
        flags.append("experience_unsegmented")

    conf["sections"] = round(heading_count / len(CANONICAL_ORDER), 2)
    return ParsedCv(cv_json=cv, confidence=conf, flags=flags, is_cv=is_cv, scanned=False)

"""Deterministic Resume-Intelligence analysis (advisory, read-only).

Extends the ATS engine with a tool taxonomy, a real structure/readability/hygiene
review (the `score()` format_flags are a stub kept for scoring stability), and an
ATS-standards linter. Everything here is an advisory signal surfaced in the
Resume-Intelligence workspace — none of it rewrites the CV, changes the numeric
`ats.score`, or feeds the truth guard. Pure functions; work in fake + live modes.
"""

from __future__ import annotations

import re

from app.pipelines.apply import ats, verbs

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\s().\-]?){7,}\d")
_STREET = re.compile(
    r"(?i)\b\d{1,5}\s+[A-Za-z][A-Za-z.]*(?:\s+[A-Za-z.]+){0,3}\s+"
    r"(?:st|street|ave|avenue|rd|road|blvd|boulevard|ln|lane|dr|drive|way|court|ct)\b"
)
_PHOTO = re.compile(r"(?i)\b(photo|photograph|headshot|picture)\b")
_FIRST_PERSON = re.compile(r"(?i)\b(i|me|my|myself|mine)\b")
_METRIC = re.compile(r"\d")
_SECTIONS = ("summary", "experience", "education", "skills", "projects", "certifications")
_WORDS_PER_PAGE = 550


def bullets_of(cv_json: dict) -> list[str]:
    """Flatten experience bullets + project descriptions from a structured CV."""
    out: list[str] = []
    for e in cv_json.get("experience") or []:
        if isinstance(e, dict):
            out.extend(str(b) for b in (e.get("bullets") or []) if str(b).strip())
    for p in cv_json.get("projects") or []:
        if isinstance(p, dict) and p.get("description"):
            out.append(str(p["description"]))
    return out


def tool_analysis(*, jd_text: str, cv_json: dict, verified_terms: list[str] | None = None) -> dict:
    """Which JD-required tools the CV represents vs. misses, plus verified tools the
    JD wants that the CV under-uses (`verified_terms` from the expanded truth corpus)."""
    # extract_keywords/critical_keywords already filter to JD skill tokens (requirement
    # zones), so use them directly — re-filtering via _has_tech_shape would drop
    # lowercased multi-char tools like kubernetes/postgresql/docker.
    keywords = ats.extract_keywords(jd_text)
    critical = ats.critical_keywords(jd_text)
    required = list(dict.fromkeys([*critical, *keywords]))
    cv_tokens = ats._cv_tokens(ats._cv_text(cv_json))
    represented = [k for k in required if ats._keyword_matches(k, "", cv_tokens)]
    missing = [k for k in required if k not in represented]
    jd_low = (jd_text or "").lower()
    underutilized = [
        v for v in (verified_terms or [])
        if not ats._keyword_matches(v, "", cv_tokens) and v.lower() in jd_low
    ]
    return {
        "required": required,
        "represented": represented,
        "missing": missing,
        "underutilized_verified": underutilized,
    }


def structure_review(*, cv_text: str, cv_json: dict) -> dict:
    """Real (heuristic) structure + ATS-hygiene review of the raw CV text."""
    text = cv_text or ""
    low = text.lower()
    wc = len(re.findall(r"\w+", text))
    est_pages = max(1, round(wc / _WORDS_PER_PAGE)) if wc else 0
    headings = [s for s in _SECTIONS if re.search(rf"(?i)\b{s}\b", text)]
    summary_present = bool(re.search(r"(?i)\b(summary|profile)\b", text))
    uses_objective = "objective" in low and not summary_present
    contact = {
        "email": bool(_EMAIL.search(text)),
        "phone": bool(_PHONE.search(text)),
        "linkedin": "linkedin.com" in low,
        "github": "github.com" in low,
    }
    bl = bullets_of(cv_json)
    first_person = len(_FIRST_PERSON.findall(text))

    flags: list[dict] = []

    def flag(code: str, message: str, severity: str = "warn") -> None:
        flags.append({"code": code, "severity": severity, "message": message})

    if _STREET.search(text):
        flag("full_address", "Full street address detected — use city/region only for privacy + ATS.")
    if _PHOTO.search(text):
        flag("photo", "Possible photo/headshot reference — remove it; photos break many ATS parsers.")
    if uses_objective:
        flag("objective", "Uses an 'Objective' — replace with a role-focused professional Summary.")
    if not summary_present:
        flag("no_summary", "No professional summary found — add a concise, role-targeted summary.", "info")
    if not contact["email"]:
        flag("no_email", "No email detected in the contact area.")
    if est_pages > 2:
        flag("length", f"~{est_pages} pages — tighten toward 1–2 (one page under ~5 years' experience).")
    if first_person > 3:
        flag("first_person", "Frequent first-person pronouns (I/my) — use implied-subject bullets.", "info")

    return {
        "word_count": wc,
        "est_pages": est_pages,
        "headings": headings,
        "summary_present": summary_present,
        "uses_objective": uses_objective,
        "contact": contact,
        "bullet_count": len(bl),
        "first_person_count": first_person,
        "ats_flags": flags,
    }


def ats_lint(*, cv_json: dict, breakdown: dict, structure: dict, weak_verbs: list[dict]) -> dict:
    """ATS-standards findings (advisory warnings, never blockers)."""
    findings: list[dict] = []

    def add(code: str, message: str, severity: str = "warn") -> None:
        findings.append({"code": code, "severity": severity, "message": message})

    # Structure hygiene bubbles up (photo/address/objective/length) already computed.
    for f in structure.get("ats_flags", []):
        findings.append(f)

    if not structure.get("summary_present"):
        add("summary_missing", "Add a professional summary tailored to the target role (not a generic objective).")
    if weak_verbs:
        add("weak_verbs", f"{len(weak_verbs)} bullet(s) open with weak verbs — strengthen where it stays truthful.")

    coverage = breakdown.get("coverage", 0) or 0
    if coverage < 0.5:
        add("low_coverage", "Naturally weave in more of the JD's required skills you genuinely have.")

    # Achievement density: bullets that state an outcome/metric.
    bl = bullets_of(cv_json)
    if bl:
        with_metric = sum(1 for b in bl if _METRIC.search(b))
        if with_metric / len(bl) < 0.2:
            add("few_outcomes", "Few bullets show a measurable outcome — add real numbers where you have them (never invent).", "info")

    # Keyword stuffing: the same skill repeated many times.
    matched = breakdown.get("matched_keywords", [])
    cv_low = ats._cv_text(cv_json)
    for kw in matched:
        if cv_low.count(kw.lower()) >= 6:
            add("keyword_stuffing", f"'{kw}' appears very frequently — avoid keyword stuffing; keep it natural.")
            break

    return {"findings": findings, "count": len(findings)}

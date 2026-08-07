"""Deterministic CV parser — 'honest 80%' text → structured cv_json.

Covers: full-CV extraction (dated experience + contact + canonical sections), header
aliasing, unicode normalization, the scanned gate, and the non-CV flag.
"""

from app.cv_engine.ingest import parse_cv_text
from app.cv_engine.ingest.canonical import match_header
from app.cv_engine.ingest.normalize import normalize_text

FULL_CV = """Ada Hunter
Backend Engineer
ada@example.com  |  +234 800 000 0000  |  linkedin.com/in/adahunter  |  github.com/adahunter

PROFESSIONAL SUMMARY
Backend engineer who builds production systems in Go and Kubernetes.

WORK EXPERIENCE
Senior Backend Engineer — Streamline
Jan 2020 - Present
- Built Go microservices serving 10k RPS
- Reduced latency by 40%

Backend Engineer, Acme Corp
2017 – 2019
• Designed Postgres schemas
• Shipped REST APIs

SKILLS
Go, Kubernetes, Postgres, gRPC, Docker

EDUCATION
BSc Computer Science — University of Lagos
2013 - 2017
"""


def test_parses_a_full_cv():
    p = parse_cv_text(FULL_CV)
    assert p.is_cv and not p.scanned and p.structured_by == "deterministic"
    cv = p.cv_json
    # Contact → links
    assert cv["links"]["email"] == "ada@example.com"
    assert "linkedin" in cv["links"] and "github" in cv["links"]
    # Headline is the tagline (the name belongs on the User record)
    assert cv["headline"] == "Backend Engineer"
    # Canonical sections
    assert cv["summary"].startswith("Backend engineer")
    assert set(["Go", "Kubernetes", "Postgres"]) <= set(cv["skills"])
    # Dated experience with title + company, dates normalized to ' -- '
    exp = cv["experience"]
    assert len(exp) == 2
    assert exp[0]["title"] == "Senior Backend Engineer" and exp[0]["company"] == "Streamline"
    # Dates are recorded RAW at ingest (PATCH normalizes them to the ' -- ' form later).
    assert exp[0]["dates"] == "Jan 2020 - Present"
    assert exp[1]["dates"] == "2017 - 2019"  # en-dash normalized to hyphen at ingest
    assert p.confidence["experience"] == 1.0
    # Education
    assert cv["education"][0]["degree"] == "BSc Computer Science"
    assert cv["education"][0]["dates"] == "2013 - 2017"


def test_header_aliases_map_to_canonical():
    assert match_header("WORK HISTORY") == "experience"
    assert match_header("Professional Experience") == "experience"
    assert match_header("Technical Skills:") == "skills"
    assert match_header("PROFILE") == "summary"
    assert match_header("Academic Qualifications") == "education"
    # A sentence merely containing a section word is NOT a header
    assert match_header("I have 5 years of experience building systems") is None


def test_unicode_is_normalized():
    assert normalize_text("eﬃcient") == "efficient"        # ﬃ ligature → ffi
    assert normalize_text("2020–2024") == "2020-2024"       # en-dash → hyphen
    assert normalize_text("co‑operate") == "co-operate"  # non-breaking hyphen
    assert normalize_text("hyphen-\nated word") == "hyphenated word"  # de-hyphenate wrap


def test_scanned_or_empty_pdf_is_gated_not_guessed():
    p = parse_cv_text("   \n  \n ")
    assert p.scanned is True and p.is_cv is False and "scanned" in p.flags
    assert p.cv_json == {}


def test_non_cv_text_is_flagged():
    prose = "The quick brown fox jumps over the lazy dog. " * 20
    p = parse_cv_text(prose)
    assert p.is_cv is False and "not_a_cv" in p.flags

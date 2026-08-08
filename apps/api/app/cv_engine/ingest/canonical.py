"""Section-header canonicalization — 'Work Experience' → experience (the deferred alias map).

Resolving aliases to canonical keys AT INGEST is why Slice 2 needed no header-alias PATCH
rule: the parsed cv_json already carries canonical section keys, so build_tex renders the
canonical order. Aligns to the canonical set in render.build_tex / rendered._anchors.
"""

from __future__ import annotations

import re

# Canonical key → header aliases (lowercased). Order/keys match the render template.
SECTION_ALIASES: dict[str, list[str]] = {
    "summary": ["summary", "professional summary", "profile", "profile summary",
                "about", "about me", "objective", "career objective", "career summary"],
    "skills": ["skills", "technical skills", "core skills", "key skills",
               "core competencies", "competencies", "technologies", "technical proficiencies",
               "areas of expertise", "expertise"],
    "experience": ["experience", "work experience", "professional experience", "employment",
                   "employment history", "work history", "career history",
                   "professional background", "relevant experience"],
    "projects": ["projects", "personal projects", "selected projects", "key projects",
                 "notable projects", "side projects"],
    "education": ["education", "academic background", "academic qualifications",
                  "qualifications", "academic history"],
    "certifications": ["certifications", "certification", "licenses",
                       "licenses & certifications", "certificates", "licences"],
    "languages": ["languages", "language proficiency"],
}

# alias → canonical key (exact, normalized match).
_ALIAS_TO_KEY: dict[str, str] = {
    alias: key for key, aliases in SECTION_ALIASES.items() for alias in aliases
}

CANONICAL_ORDER = ["summary", "skills", "experience", "projects",
                   "education", "certifications", "languages"]

_WS = re.compile(r"\s+")


def match_header(line: str) -> str | None:
    """Return the canonical section key iff the whole line is a section header, else None.

    Line-anchored + strict (short line, exact alias match after trimming decoration) so a
    sentence merely containing 'experience' is never mistaken for a header."""
    s = (line or "").strip()
    if not s or len(s) > 40:  # real headers are short
        return None
    low = _WS.sub(" ", s.lower())
    low = re.sub(r"^[^a-z]+|[^a-z]+$", "", low)  # trim leading/trailing decoration
    return _ALIAS_TO_KEY.get(low)

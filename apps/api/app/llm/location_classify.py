"""Location eligibility — can a candidate based in Nigeria actually apply to this job?

Deterministic, text-based (there is no structured remote/country field on a posting —
only free-text ``location`` + ``description``). Mirrors ``experience_classify`` (regex
phrases, first match wins) rather than a bag-of-words classifier, because eligibility
hinges on phrases and negation ("must be authorized to work in the US", "US only").

Lenient by design: keep remote / Nigeria / Africa / worldwide roles AND anything
ambiguous or unstated (benefit of the doubt); drop only the clear blockers — foreign
work authorization, foreign-remote locks, and concrete onsite-abroad postings.
"""

from __future__ import annotations

import re

# --- Clear blockers: a candidate in Nigeria cannot apply. -------------------------
_BLOCK = [
    # Foreign work authorization / citizenship / clearance.
    r"must be (?:legally )?(?:authori[sz]ed|eligible|permitted) to work in (?:the )?"
    r"(?:us|u\.s\.|usa|united states|uk|u\.k\.|united kingdom|eu|europe|canada|australia)",
    r"\b(?:us|u\.s\.|uk|u\.k\.|eu|canadian|australian) work (?:authori[sz]ation|permit|visa)\b",
    r"(?:authori[sz]ation|eligibility) to work in the (?:us|united states|uk|eu|canada|australia)",
    r"\b(?:american|u\.?s\.?|uk|british|eu|european|canadian|australian) citizens? only\b",
    r"\bmust be (?:a |an )?(?:us|u\.s\.|uk|eu|canadian|australian) (?:citizen|resident|national)\b",
    r"\bgreen card\b",
    r"\bsecurity clearance\b",
    r"\b(?:no|without) visa sponsorship\b",
    r"\bvisa sponsorship (?:is )?not (?:available|offered|provided)\b",
    # Foreign-remote locks — "remote" but restricted to a non-Nigeria country.
    r"remote\s*[\(,-]?\s*(?:us|u\.s\.|usa|united states|uk|u\.k\.|eu|europe|canada)"
    r"(?:[- ]?based)?\s*only",
    r"\b(?:us|u\.s\.|usa|uk|eu)[- ]remote\b",
    r"\bremote[ -](?:united states|usa|us only|uk only)\b",
    r"\b(?:us|u\.s\.|uk|eu)[- ]based only\b",
]
_BLOCK_RE = [re.compile(p) for p in _BLOCK]

# --- Positive signals: clearly appliable from Nigeria. ----------------------------
_ALLOW = [
    r"\b(?:nigeria|nigerian|naija|lagos|abuja|ibadan|kano|port[- ]?harcourt)\b",
    r"\bafrica\b|\bafrican\b|\bemea\b",
    r"\bremote\b[^.]*\b(?:worldwide|global|globally|anywhere|international|internationally)\b",
    r"\b(?:worldwide|global|globally|anywhere|international)\b[^.]*\bremote\b",
    r"\bwork from anywhere\b",
    r"\b(?:fully|100%|100 %) remote\b",
]
_ALLOW_RE = [re.compile(p) for p in _ALLOW]

# Any "remote-ish" signal anywhere in the posting means it's not a fixed onsite role.
_REMOTE_ISH = re.compile(
    r"\b(?:remote|anywhere|worldwide|globally|distributed|virtual|work from home|wfh)\b"
)
# Nigeria / Africa tokens used to tell a home-region location from a foreign one.
_NG_AFRICA = re.compile(
    r"\b(?:nigeria|nigerian|naija|lagos|abuja|ibadan|kano|port[- ]?harcourt"
    r"|africa|african|emea)\b"
)


def _is_foreign_onsite(location_lc: str, text_lc: str) -> bool:
    """True when the posting names a concrete location that isn't Nigeria/Africa and
    carries no remote signal anywhere — i.e. onsite abroad. A blank/ambiguous location
    is NOT foreign onsite (kept under the lenient default)."""
    if _REMOTE_ISH.search(text_lc):
        return False
    loc = location_lc.strip()
    if not loc or loc in {"-", "—", "n/a"}:
        return False
    return not _NG_AFRICA.search(loc)


def is_appliable_from_nigeria(
    *, title: str, location: str | None, description: str | None
) -> bool:
    """Whether a Nigeria-based candidate can realistically apply. Lenient: keep unless
    there's a clear blocker (foreign work-auth, foreign-remote lock, onsite abroad)."""
    text = f"{title or ''} {location or ''} {description or ''}".lower()
    loc = (location or "").lower()

    if any(p.search(text) for p in _BLOCK_RE):
        return False
    if any(p.search(text) for p in _ALLOW_RE):
        return True
    if _is_foreign_onsite(loc, text):
        return False
    return True  # lenient default — remote-unspecified, blank, or ambiguous

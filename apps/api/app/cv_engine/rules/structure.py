"""Bucket 2 — Structure rules (draft phase, deterministic).

These wrap the existing, test-locked deterministic analysis
(`intel.structure_review`, `verbs.detect`) as registry Rules so structure
professionalism is one source of truth, not a parallel checklist.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.cv_engine.fixes.deterministic import normalize_date_string, tidy_value
from app.cv_engine.rules.base import FixMode, Phase, Rule, RuleContext, Severity, Violation
from app.pipelines.apply import intel, verbs


def _summary_present(ctx: RuleContext) -> Iterable[Violation]:
    if not (ctx.cv_json.get("summary") or "").strip():
        yield Violation(
            rule_id="structure.summary_present",
            severity=Severity.major,
            message="No professional summary — add a concise, role-targeted summary.",
            fix_hint="Write a 2–3 line summary anchored to the target role, from real experience.",
        )


def _experience_present(ctx: RuleContext) -> Iterable[Violation]:
    if not (ctx.cv_json.get("experience") or []):
        yield Violation(
            rule_id="structure.experience_present",
            severity=Severity.major,
            message="No experience section — the CV has no work history to tailor from.",
            fix_hint="Add at least one role with dated, outcome-focused bullets.",
        )


def _contact_present(ctx: RuleContext) -> Iterable[Violation]:
    links = ctx.cv_json.get("links") or {}
    if not any(str(v).strip() for v in links.values()):
        yield Violation(
            rule_id="structure.contact_present",
            severity=Severity.major,
            message="No contact/link found — a recruiter can't reach you.",
            fix_hint="Add at least one reachable contact (email, LinkedIn, or portfolio link).",
        )


def _no_first_person(ctx: RuleContext) -> Iterable[Violation]:
    if ctx.structure().get("first_person_count", 0) > 3:
        yield Violation(
            rule_id="structure.no_first_person",
            severity=Severity.minor,
            message="Frequent first-person pronouns (I/my) — use implied-subject bullets.",
            fix_hint="Rewrite bullets to open with a strong verb, dropping I/my/me.",
        )


def _strong_verbs(ctx: RuleContext) -> Iterable[Violation]:
    weak = verbs.detect(intel.bullets_of(ctx.cv_json))
    for w in weak:
        yield Violation(
            rule_id="structure.strong_verbs",
            severity=Severity.minor,
            message=f"Bullet opens with a weak verb ('{w['weak_verb']}').",
            fix_hint="Stronger, still-truthful openers: " + ", ".join(w["suggestions"]),
            span={"where": "bullet", "text": w["bullet"]},
        )


def _date_format(ctx: RuleContext) -> Iterable[Violation]:
    """Non-canonical dates (deterministically fixable → normalized in PATCH)."""
    cv = ctx.cv_json
    for section in ("experience", "education"):
        for e in cv.get(section) or []:
            if not isinstance(e, dict):
                continue
            values = [e["dates"]] if e.get("dates") else [
                e[k] for k in ("start", "end") if e.get(k)
            ]
            for v in values:
                norm = normalize_date_string(str(v))
                if norm and norm != str(v):
                    yield Violation(
                        rule_id="structure.date_format", severity=Severity.minor,
                        message=f"Date '{v}' isn't in a consistent format.",
                        fix_hint=f"Normalize to '{norm}'.",
                        span={"where": section, "before": str(v), "after": norm},
                    )


def _clean_text(ctx: RuleContext) -> Iterable[Violation]:
    """Whitespace / stray bullet-glyph hygiene (deterministically fixable in PATCH)."""
    cv = ctx.cv_json
    values: list = []
    if cv.get("summary"):
        values.append(cv["summary"])
    for e in cv.get("experience") or []:
        if isinstance(e, dict):
            values.extend(e.get("bullets") or [])
    for p in cv.get("projects") or []:
        if isinstance(p, dict) and p.get("description"):
            values.append(p["description"])
    if any(tidy_value(v) != str(v) for v in values):
        yield Violation(
            rule_id="structure.clean_text", severity=Severity.minor,
            message="Some text has inconsistent spacing or stray bullet characters.",
            fix_hint="Trim whitespace and remove leading bullet glyphs.",
        )


RULES: list[Rule] = [
    Rule(
        id="structure.summary_present", severity=Severity.major, phase=Phase.draft,
        fix_mode=FixMode.agent, weight=2.0, check=_summary_present,
        constraint="Include a concise, role-targeted summary (never a generic objective).",
        fix_hint="Add a 2–3 line role-anchored summary from real experience.",
    ),
    Rule(
        id="structure.experience_present", severity=Severity.major, phase=Phase.draft,
        fix_mode=FixMode.user, weight=3.0, check=_experience_present,
        constraint="Every CV must present real work history; never fabricate roles.",
        fix_hint="Add at least one real role with dated bullets.",
    ),
    Rule(
        id="structure.contact_present", severity=Severity.major, phase=Phase.draft,
        fix_mode=FixMode.user, weight=2.0, check=_contact_present,
        constraint="A reachable contact (email/LinkedIn/portfolio) must be present.",
        fix_hint="Add a reachable contact link.",
    ),
    Rule(
        id="structure.no_first_person", severity=Severity.minor, phase=Phase.draft,
        fix_mode=FixMode.agent, weight=0.5, check=_no_first_person,
        constraint="Use implied-subject bullets; do not use first-person pronouns (I/my/me).",
        fix_hint="Open bullets with a strong verb, dropping I/my/me.",
    ),
    Rule(
        id="structure.strong_verbs", severity=Severity.minor, phase=Phase.draft,
        fix_mode=FixMode.agent, weight=0.5, check=_strong_verbs,
        constraint="Open bullets with a strong action verb (led/built/engineered, not managed).",
        fix_hint="Replace weak openers with stronger, still-truthful verbs.",
    ),
    Rule(
        id="structure.date_format", severity=Severity.minor, phase=Phase.draft,
        fix_mode=FixMode.deterministic, weight=0.5, check=_date_format,
        constraint="Use a consistent date format (e.g. 'Jan 2020 -- Present').",
        fix_hint="Normalize dates to a consistent 'Mon YYYY -- Mon YYYY' form.",
    ),
    Rule(
        id="structure.clean_text", severity=Severity.minor, phase=Phase.draft,
        fix_mode=FixMode.deterministic, weight=0.5, check=_clean_text,
        constraint="No stray bullet glyphs or irregular whitespace in content.",
        fix_hint="Trim whitespace and remove leading bullet characters.",
    ),
]

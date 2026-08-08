"""Bucket 1 — Grounding (the deterministic hallucination seal).

Every number and proper-noun entity in the CV's *narrative* content (summary,
experience bullets, titles/companies, projects, education) must trace to the
ledger — the closed set of truths the content may draw from. This is a plain
string check over a closed fact set, not a model behaving: a fabricated metric
or employer cannot talk past a regex (spec §5, doors #1 and #6). Critical
severity, no override.

Scope note (slice 1): skills-grounding ("claimed skill not evidenced") is handled
separately by the existing ats_vet path and is out of scope here. This runs at the
DRAFT phase on the structured cv_json, so it is deterministic and needs no compile.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.cv_engine.rules.base import FixMode, Phase, Rule, RuleContext, Severity, Violation

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"[A-Za-z0-9&.+#\-]+")
_MONTHS = {
    "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct",
    "nov", "dec", "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
}
_SECTION_WORDS = {
    "summary", "skills", "experience", "projects", "education", "certifications", "languages",
}


def _num(token: str) -> str:
    """Normalize a numeric token to its digit core: '1,000'→'1000', '99.9%'→'99.9'."""
    return token.replace(",", "").rstrip(".")


def _tok(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def _numbers(text: str) -> set[str]:
    return {_num(m.group(0)) for m in _NUMBER.finditer(text or "")}


def _ledger_text(ledger: list[dict]) -> str:
    parts: list[str] = []
    for fact in ledger or []:
        parts.append(str(fact.get("text") or ""))
        payload = fact.get("payload") or {}
        if isinstance(payload, dict):
            parts.extend(str(v) for v in payload.values())
        else:
            parts.append(str(payload))
    return "  ".join(parts)


def _content_strings(cv_json: dict) -> list[str]:
    """The narrative content grounding governs (never section headers or skills)."""
    out: list[str] = []
    if cv_json.get("summary"):
        out.append(str(cv_json["summary"]))
    for e in cv_json.get("experience") or []:
        if isinstance(e, dict):
            out.append(str(e.get("title") or ""))
            out.append(str(e.get("role") or ""))
            out.append(str(e.get("company") or ""))
            out += [str(b) for b in (e.get("bullets") or [])]
    for p in cv_json.get("projects") or []:
        if isinstance(p, dict):
            out += [str(p.get("name") or ""), str(p.get("description") or "")]
    for ed in cv_json.get("education") or []:
        if isinstance(ed, str):
            out.append(ed)
        elif isinstance(ed, dict):
            out.append(str(ed.get("degree") or ""))
            out.append(str(ed.get("school") or ed.get("institution") or ""))
    return [s for s in out if s.strip()]


def _entity_suspects(strings: list[str], name: str) -> list[str]:
    """Proper-noun-shaped tokens: CamelCase/acronyms/tokens with digits anywhere, plus
    mid-clause capitalized words (len≥3). Sentence-initial plain words are skipped
    (they're capitalized by position, not because they're proper nouns)."""
    name_toks = {_tok(w) for w in (name or "").split()}
    suspects: list[str] = []
    for s in strings:
        words = s.split()
        for i, raw in enumerate(words):
            core = raw.strip(".,;:()[]{}\"'")
            norm = _tok(core)
            if len(norm) < 3 or norm in _MONTHS or norm in _SECTION_WORDS or norm in name_toks:
                continue
            if not any(c.isalpha() for c in norm):
                continue  # pure numbers/percentages are the numbers rule's job, not entities
            internal = any(c.isupper() for c in core[1:]) or any(c.isdigit() for c in core)
            if internal:
                suspects.append(core)
            elif core[0].isupper() and i > 0:  # mid-clause capitalized → likely proper noun
                suspects.append(core)
    # Preserve order, dedupe by normalized form.
    seen, ordered = set(), []
    for s in suspects:
        k = _tok(s)
        if k not in seen:
            seen.add(k)
            ordered.append(s)
    return ordered


def _numbers_verbatim(ctx: RuleContext) -> Iterable[Violation]:
    allowed = _numbers(_ledger_text(ctx.ledger))
    for s in _content_strings(ctx.cv_json):
        for token in _NUMBER.findall(s):
            if _num(token) not in allowed:
                yield Violation(
                    rule_id="grounding.numbers_verbatim", severity=Severity.critical,
                    message=f"The number '{token}' is not supported by the ledger.",
                    fix_hint="Cite a real figure from your history, or drop it.",
                    span={"where": "content", "text": s, "number": token},
                )


def _entities_verbatim(ctx: RuleContext) -> Iterable[Violation]:
    ledger_tokens = {_tok(w) for w in _WORD.findall(_ledger_text(ctx.ledger))}
    ledger_tokens.discard("")
    for entity in _entity_suspects(_content_strings(ctx.cv_json), ctx.name):
        if _tok(entity) not in ledger_tokens:
            yield Violation(
                rule_id="grounding.entities_verbatim", severity=Severity.critical,
                message=f"'{entity}' does not appear in your verified history.",
                fix_hint="Use only real employers/products/places — never invent entities.",
                span={"where": "content", "entity": entity},
            )


RULES: list[Rule] = [
    Rule(
        id="grounding.numbers_verbatim", severity=Severity.critical, phase=Phase.draft,
        fix_mode=FixMode.user, weight=5.0, check=_numbers_verbatim,
        constraint="Use ONLY numbers present in the candidate's history; never invent figures.",
        fix_hint="Cite a real figure or remove the claim.",
    ),
    Rule(
        id="grounding.entities_verbatim", severity=Severity.critical, phase=Phase.draft,
        fix_mode=FixMode.user, weight=5.0, check=_entities_verbatim,
        constraint="Use ONLY employers/products/institutions present in the candidate's history.",
        fix_hint="Use only real entities from the ledger.",
    ),
]

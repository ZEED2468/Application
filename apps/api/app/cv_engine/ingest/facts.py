"""Build the fact ledger — the closed set of truths content may cite.

Ingest RECORDS; it never judges (invariant #1). In fresh-build the ledger is derived
from the profile's cv_json (so, before any agent tailoring exists, the CV trivially
grounds against it). A run may instead carry an explicit `ledger` — the independent
truth source that makes the grounding seal meaningful (fixtures, and later uploads /
`needs_input` answers). The normalized/derived-arithmetic ledger and provenance graph
(`derived_from`) grow in later slices; here we keep a flat, honest record.
"""

from __future__ import annotations

import re

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def _fact(
    kind: str, text: str, *, idx: int, source: str = "profile", payload: dict | None = None
) -> dict:
    return {
        "id": f"f_{kind}_{idx}",
        "kind": kind,
        "text": text,
        "source": source,
        "payload": payload or {},
        "derived_from": [],
    }


def _normalize(facts: list) -> list[dict]:
    out: list[dict] = []
    for i, f in enumerate(facts or []):
        if isinstance(f, str):
            out.append(_fact("note", f, idx=i, source="upload"))
        elif isinstance(f, dict):
            out.append({
                "id": f.get("id") or f"f_{f.get('kind', 'note')}_{i}",
                "kind": f.get("kind", "note"),
                "text": str(f.get("text") or ""),
                "source": f.get("source", "upload"),
                "payload": f.get("payload") or {},
                "derived_from": f.get("derived_from") or [],
            })
    return out


def _from_cv_json(cv_json: dict) -> list[dict]:
    facts: list[dict] = []

    def add(kind: str, text, *, payload: dict | None = None) -> None:
        facts.append(_fact(kind, str(text), idx=len(facts), payload=payload))

    if cv_json.get("summary"):
        add("summary", cv_json["summary"])
    for e in cv_json.get("experience") or []:
        if not isinstance(e, dict):
            continue
        title = " ".join(filter(None, [e.get("title") or e.get("role"), "at", e.get("company")]))
        bullets = " ".join(str(b) for b in (e.get("bullets") or []))
        add("role", f"{title}. {bullets}".strip(), payload={
            "company": e.get("company"), "dates": e.get("dates"),
            "start": e.get("start"), "end": e.get("end"),
        })
    for p in cv_json.get("projects") or []:
        if isinstance(p, dict):
            add("project", " ".join(filter(None, [p.get("name"), p.get("description")])))
    for ed in cv_json.get("education") or []:
        text = ed if isinstance(ed, str) else " ".join(
            filter(None, [ed.get("degree"), ed.get("school") or ed.get("institution"),
                          ed.get("dates")])
        )
        add("education", text)
    for s in cv_json.get("skills") or []:
        add("skill", s)
    for label, val in (cv_json.get("links") or {}).items():
        if str(val).strip():
            add("link", val, payload={"label": label})
    return facts


def _years_in(value) -> list[int]:
    return [int(m.group(0)) for m in _YEAR.finditer(str(value or ""))]


def _derived_facts(base: list[dict]) -> list[dict]:
    """Derived-arithmetic facts (Slice 11): a computed total the base facts only imply.

    Career span = latest year seen across the roles minus the earliest — a total the CV can cite
    truthfully ("N years experience") even though no single date states it. Carries `derived_from`
    edges to every role it aggregated; its number enters grounding's allowed set like any payload
    number (grounding is per-token, so it grounds the digit, not the semantics — a known limit)."""
    roles = [f for f in base if f.get("kind") == "role"]
    years: list[int] = []
    for f in roles:
        payload = f.get("payload") or {}
        for key in ("dates", "start", "end"):
            years += _years_in(payload.get(key))
        years += _years_in(f.get("text"))
    if len(set(years)) < 2:
        return []
    span = max(years) - min(years)
    if span <= 0:
        return []
    return [_fact(
        "metric", f"{span} years experience", idx=len(base), source="derived",
        payload={"years": span, "from": min(years), "to": max(years)},
    ) | {"derived_from": [f["id"] for f in roles]}]


def build_ledger(run_input: dict) -> list[dict]:
    """Return the run's ledger: an explicit `ledger` if provided, else derived from cv_json, plus
    any derived-arithmetic facts computed from the base set."""
    explicit = (run_input or {}).get("ledger")
    cv_json = (run_input or {}).get("cv_json") or {}
    base = _normalize(explicit) if explicit else _from_cv_json(cv_json)
    return base + _derived_facts(base)

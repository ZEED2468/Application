"""Build the fact ledger — the closed set of truths content may cite.

Ingest RECORDS; it never judges (invariant #1). In fresh-build the ledger is derived
from the profile's cv_json (so, before any agent tailoring exists, the CV trivially
grounds against it). A run may instead carry an explicit `ledger` — the independent
truth source that makes the grounding seal meaningful (fixtures, and later uploads /
`needs_input` answers). The normalized/derived-arithmetic ledger and provenance graph
(`derived_from`) grow in later slices; here we keep a flat, honest record.
"""

from __future__ import annotations


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


def build_ledger(run_input: dict) -> list[dict]:
    """Return the run's ledger: an explicit `ledger` if provided, else derived from cv_json."""
    explicit = (run_input or {}).get("ledger")
    if explicit:
        return _normalize(explicit)
    return _from_cv_json((run_input or {}).get("cv_json") or {})

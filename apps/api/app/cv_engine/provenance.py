"""Provenance — link every derived/transformed change back to the source ledger fact(s).

Slice 8. Populates the `derived_from` graph the ledger stubbed out. Each PATCH/repair FixRecord
(`{rule_id, field, before, after}`) gains a `source` list of ledger fact ids, computed from the
record's `field` path + the deterministic `f_{kind}_{idx}` scheme that `ingest.facts` builds. The
inferred summary (Slice 7) additionally becomes a derived ledger fact carrying `derived_from`.

Best-effort: when the ledger is an explicit upload with untyped `note` facts, a change may have no
resolvable source (`source: []`). The closure seal only asserts that any *cited* source is a real
ledger fact — content can never originate from a third source.
"""

from __future__ import annotations

import re

# A FixRecord field path: section, optional [index], optional .subfield.
_FIELD = re.compile(r"^(?P<section>\w+)(?:\[(?P<idx>\d+)\])?(?:\.(?P<sub>\w+))?$")

# cv_json section -> the ledger fact kind it produces (see facts._from_cv_json).
_SECTION_KIND = {
    "experience": "role", "projects": "project", "education": "education",
    "summary": "summary", "skills": "skill", "links": "link",
}


def _by_kind(ledger: list[dict], kind: str) -> list[dict]:
    return [f for f in (ledger or []) if f.get("kind") == kind]


def source_for(record: dict, ledger: list[dict]) -> list[str]:
    """The ledger fact id(s) a FixRecord derived from (best-effort; [] when unresolvable)."""
    rule = record.get("rule_id", "") or ""
    field = record.get("field", "") or ""

    # A summary written/inferred from the whole history (composed from role + skill facts).
    if rule in ("agent.write_summary", "agent.infer_summary"):
        return [f["id"] for f in _by_kind(ledger, "role") + _by_kind(ledger, "skill")]
    # A bullet rewrite carries no [i] — match the source role fact by the `before` text.
    if rule == "agent.rewrite_bullet":
        before = str(record.get("before") or "")
        if not before:
            return []
        return [f["id"] for f in _by_kind(ledger, "role") if before in (f.get("text") or "")][:1]
    # Page-fit trim is coarse / removal-only — no single source.
    if rule == "agent.trim_to_fit":
        return []

    m = _FIELD.match(field)
    if not m:
        return []
    kind = _SECTION_KIND.get(m.group("section"))
    if not kind:
        return []
    if kind == "link":                              # field = links.<label>
        label = m.group("sub")
        return [f["id"] for f in _by_kind(ledger, "link")
                if (f.get("payload") or {}).get("label") == label][:1]
    if kind == "summary":
        got = _by_kind(ledger, "summary")
        return [got[0]["id"]] if got else []
    idx = int(m.group("idx")) if m.group("idx") is not None else 0
    facts = _by_kind(ledger, kind)
    return [facts[idx]["id"]] if idx < len(facts) else []


def annotate(records: list[dict], ledger: list[dict]) -> list[dict]:
    """Attach `source` (the derived_from edge) to each FixRecord in place; return the list."""
    for r in records:
        r["source"] = source_for(r, ledger)
    return records


def derived_summary_fact(summary: str, source_ids: list[str], ledger: list[dict]) -> dict:
    """A ledger fact for an inferred summary, carrying its `derived_from` edges."""
    n = sum(1 for f in (ledger or []) if f.get("kind") == "summary")
    return {
        "id": f"f_summary_d{n}", "kind": "summary", "text": str(summary),
        "source": "derived", "payload": {}, "derived_from": list(source_ids),
    }

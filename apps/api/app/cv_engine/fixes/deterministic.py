"""Deterministic cv_json transforms for the PATCH phase.

Every function is pure — it returns a NEW cv_json plus a list of FixRecord dicts
(``{"rule_id","field","before","after"}``) describing what changed. Grounding-safe:
they only reformat/trim existing strings and never introduce a number or entity, so a
patched cv_json still passes ``grounding`` against the original-input ledger.
"""

from __future__ import annotations

import copy
import re

FixRecord = dict  # {"rule_id": str, "field": str, "before": str, "after": str}

# --- Date normalization -------------------------------------------------------------

_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_MONTH_INDEX: dict[str, int] = {ab.lower(): i for i, ab in enumerate(_MONTH_ABBR, 1)}
_MONTH_INDEX.update({
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "sept": 9, "october": 10,
    "november": 11, "december": 12,
})
_PRESENT = {"present", "current", "now", "ongoing", "till date", "to date", "todate"}
_RANGE_SPLIT = re.compile(r"\s*[-/]\s*")


def _parse_token(s: str) -> str | None:
    """Normalize a single date token → 'YYYY' / 'Mon YYYY' / 'Present', else None."""
    s = (s or "").strip().strip(".,")
    if not s:
        return None
    if s.lower() in _PRESENT:
        return "Present"
    if re.fullmatch(r"\d{4}", s):
        return s
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{4})", s)  # MM/YYYY
    if m and 1 <= int(m.group(1)) <= 12:
        return f"{_MONTH_ABBR[int(m.group(1)) - 1]} {m.group(2)}"
    m = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})", s)  # YYYY-MM
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{_MONTH_ABBR[int(m.group(2)) - 1]} {m.group(1)}"
    m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{4})", s)  # Mon YYYY / Month YYYY
    if m:
        idx = _MONTH_INDEX.get(m.group(1).lower())
        if idx:
            return f"{_MONTH_ABBR[idx - 1]} {m.group(2)}"
    return None


def normalize_date_string(s: str) -> str | None:
    """Canonical date or ' -- '-joined range, or None if it can't be parsed
    (already-canonical or unrecognized inputs return None → left untouched)."""
    s = (s or "").strip()
    if not s:
        return None
    tok = _parse_token(s)
    if tok:
        return tok
    norm = s.replace("–", "-").replace("—", "-").replace("−", "-")
    norm = re.sub(r"\s+to\s+", " - ", norm, flags=re.I)
    parts = _RANGE_SPLIT.split(norm, maxsplit=1)
    if len(parts) == 2:
        left, right = _parse_token(parts[0]), _parse_token(parts[1])
        if left and right:
            return f"{left} -- {right}"
    return None


def _fix_date(entry: dict, key: str, field: str, fixes: list[FixRecord]) -> None:
    before = str(entry.get(key) or "")
    after = normalize_date_string(before)
    if after and after != before:
        entry[key] = after
        fixes.append({"rule_id": "structure.date_format", "field": field,
                      "before": before, "after": after})


def normalize_dates(cv_json: dict) -> tuple[dict, list[FixRecord]]:
    cv = copy.deepcopy(cv_json)
    fixes: list[FixRecord] = []
    for section in ("experience", "education"):
        for i, entry in enumerate(cv.get(section) or []):
            if not isinstance(entry, dict):
                continue
            if entry.get("dates"):
                _fix_date(entry, "dates", f"{section}[{i}].dates", fixes)
            else:
                for key in ("start", "end"):
                    if entry.get(key):
                        _fix_date(entry, key, f"{section}[{i}].{key}", fixes)
    return cv, fixes


# --- Text / whitespace tidy ---------------------------------------------------------

_WS = re.compile(r"\s+")
_LEAD_BULLET = re.compile(r"^[\-\*•‣◦⁃∙·\s]+")


def tidy_value(s) -> str:
    """Strip leading bullet glyphs (the template adds its own) + collapse whitespace."""
    return _WS.sub(" ", _LEAD_BULLET.sub("", str(s or ""))).strip()


def tidy_text(cv_json: dict) -> tuple[dict, list[FixRecord]]:
    cv = copy.deepcopy(cv_json)
    fixes: list[FixRecord] = []
    if cv.get("summary"):
        before = str(cv["summary"])
        after = tidy_value(before)
        if after != before:
            cv["summary"] = after
            fixes.append({"rule_id": "structure.clean_text", "field": "summary",
                          "before": before, "after": after})
    for i, e in enumerate(cv.get("experience") or []):
        if not isinstance(e, dict) or not e.get("bullets"):
            continue
        before = list(e["bullets"])
        after = [tidy_value(b) for b in before]
        after = [b for b in after if b]  # drop empties
        if after != [str(b) for b in before]:
            e["bullets"] = after
            fixes.append({"rule_id": "structure.clean_text", "field": f"experience[{i}].bullets",
                          "before": " | ".join(str(b) for b in before), "after": " | ".join(after)})
    for i, p in enumerate(cv.get("projects") or []):
        if isinstance(p, dict) and p.get("description"):
            before = str(p["description"])
            after = tidy_value(before)
            if after != before:
                p["description"] = after
                fixes.append({"rule_id": "structure.clean_text",
                              "field": f"projects[{i}].description",
                              "before": before, "after": after})
    return cv, fixes


# --- Link tidy ----------------------------------------------------------------------


def _tidy_link(v: str) -> str:
    v = str(v or "").strip()
    if not v or ("@" in v and "://" not in v):  # empty or an email — leave alone
        return v
    has_scheme = re.match(r"^[a-z][a-z0-9+.-]*://", v, re.I)
    if not has_scheme and re.match(r"^[\w.-]+\.[a-z]{2,}", v, re.I):
        v = "https://" + v
    m = re.match(r"^(https?://)([^/]+)(.*)$", v, re.I)
    if m:
        v = m.group(1).lower() + m.group(2).lower() + m.group(3)
    return v


def tidy_links(cv_json: dict) -> tuple[dict, list[FixRecord]]:
    cv = copy.deepcopy(cv_json)
    fixes: list[FixRecord] = []
    links = cv.get("links")
    if isinstance(links, dict):
        for k, v in list(links.items()):
            before = str(v or "")
            after = _tidy_link(before)
            if after != before:
                links[k] = after
                fixes.append({"rule_id": "structure.clean_text", "field": f"links.{k}",
                              "before": before, "after": after})
    return cv, fixes


# Rule → deterministic fix (the PATCH phase applies a fixable rule's transform when it fired).
FIX_MAP = {
    "structure.date_format": normalize_dates,
    "structure.clean_text": tidy_text,
}

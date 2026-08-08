"""Built-in TemplateSpecs — code-defined, versioned. `canonical` is the default fallback.

All built-ins render via the canonical single-column mold (build_tex) — they differ in
DEMAND (slot manifest) and POLICY (registry_overrides, e.g. page limit). Real per-template
layout variation comes from validated custom .tex templates. The canonical REQUIRED slot
set is kept identical to the engine's original REQUIRED_SLOTS so gap verdicts are unchanged.
"""

from __future__ import annotations

from app.cv_engine.templates.spec import Slot, TemplateSpec

# The canonical section slots (the mold's demand). Required set == the original
# REQUIRED_SLOTS (summary, experience, skills, contact).
_CANONICAL_SLOTS: tuple[Slot, ...] = (
    Slot("summary", "text", required=True, fill_from=("summary",), absence_ok="ask"),
    Slot("experience", "entries", required=True, min_items=1,
         fill_from=("role", "metric"), absence_ok="block"),
    Slot("skills", "list", required=True, fill_from=("skill",), absence_ok="ask"),
    Slot("contact", "links", required=True, fill_from=("link",), absence_ok="ask"),
    Slot("projects", "entries", fill_from=("project",), absence_ok="omit"),
    Slot("education", "entries", fill_from=("education",), absence_ok="omit"),
    Slot("certifications", "list", fill_from=("certification",), absence_ok="omit"),
    Slot("languages", "list", fill_from=("language",), absence_ok="omit"),
)

CANONICAL = TemplateSpec(
    id="canonical", version=1, name="Canonical", kind="canonical",
    slots=_CANONICAL_SLOTS, registry_overrides={"page_limit": 2},
)

COMPACT = TemplateSpec(
    id="compact", version=1, name="Compact (1 page)", kind="canonical",
    slots=_CANONICAL_SLOTS, registry_overrides={"page_limit": 1},
)

ACADEMIC = TemplateSpec(
    id="academic", version=1, name="Academic", kind="canonical",
    slots=(*_CANONICAL_SLOTS,
           Slot("publications", "entries", fill_from=("publication",), absence_ok="omit")),
    registry_overrides={"page_limit": 5},
)

BUILTINS: dict[str, TemplateSpec] = {t.id: t for t in (CANONICAL, COMPACT, ACADEMIC)}


def default_template() -> TemplateSpec:
    return CANONICAL


def slot_present(slot_id: str, cv_json: dict) -> bool:
    """Deterministic presence predicate for a slot (generalizes the original _gap_analyze)."""
    if slot_id == "contact":
        return any(str(v).strip() for v in (cv_json.get("links") or {}).values())
    val = cv_json.get(slot_id)
    if isinstance(val, str):
        return bool(val.strip())
    return bool(val)

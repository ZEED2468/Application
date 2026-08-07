"""TemplateSpec + Slot — the template as demand (slots) + policy (overrides) + a renderer.

The template defines DEMAND (which slots it requires/offers); the ledger defines supply;
inference only matches them. `registry_overrides` is per-template policy the rules read
(e.g. `{"page_limit": 5}` for an academic CV). A run pins `(id, version)`, so the exact
spec is refetchable and deltas are attributable.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Slot:
    id: str                       # a cv_json section key, or a derived slot (e.g. "contact")
    kind: str                     # display/grouping hint
    required: bool = False
    min_items: int = 0
    fill_from: tuple[str, ...] = ()   # fact kinds this slot may draw from (Slice 7 inference)
    absence_ok: str = "ask"       # omit | ask | block — what to do when a required slot is empty

    def to_dict(self) -> dict:
        return {
            "id": self.id, "kind": self.kind, "required": self.required,
            "min_items": self.min_items, "fill_from": list(self.fill_from),
            "absence_ok": self.absence_ok,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Slot:
        return cls(
            id=d["id"], kind=d.get("kind", "custom"), required=bool(d.get("required")),
            min_items=int(d.get("min_items", 0)), fill_from=tuple(d.get("fill_from") or ()),
            absence_ok=d.get("absence_ok", "ask"),
        )


@dataclass(frozen=True)
class TemplateSpec:
    id: str                       # stable ref: a built-in id ("canonical") or a cv_template uuid
    version: int
    name: str
    kind: str = "canonical"       # canonical | latex
    track: str | None = None
    slots: tuple[Slot, ...] = ()
    registry_overrides: dict = field(default_factory=dict)
    latex: str | None = None      # the custom .tex (kind == "latex")
    layout: dict = field(default_factory=dict)

    @property
    def page_limit(self) -> int:
        return int(self.registry_overrides.get("page_limit", 2))

    def required_slots(self) -> tuple[Slot, ...]:
        return tuple(s for s in self.slots if s.required)

    def summary(self) -> dict:
        """A UI-facing summary (no raw latex)."""
        return {
            "id": self.id, "version": self.version, "name": self.name,
            "kind": self.kind, "track": self.track,
            "slots": [s.to_dict() for s in self.slots],
            "registry_overrides": self.registry_overrides,
        }

"""Rule registry primitives: Severity, Phase, FixMode, Violation, RuleContext, Rule, Registry.

One `Rule` object drives the executable check now and (later slices) the agent's
prompt constraint + the repair instruction. Config-only variation belongs in the
DB; the logic lives here in code. The `Registry.version()` hash is pinned per run so
score history is attributable ("rules changed", never a false regression).
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from app.cv_engine.templates.spec import TemplateSpec
from app.pipelines.apply import ats, intel


class Severity(str, enum.Enum):
    critical = "critical"  # blocks; caps the score at 0 — no override
    major = "major"        # blocks, but repairable
    minor = "minor"        # annotates only; never blocks release


class Phase(str, enum.Enum):
    draft = "draft"        # runs on the structured cv_json (pre-render)
    rendered = "rendered"  # runs on text extracted from the compiled PDF


class FixMode(str, enum.Enum):
    deterministic = "deterministic"
    agent = "agent"
    user = "user"  # needs_input — never falls back to generation
    na = "na"      # encoded by construction (the template is the mold)


_BLOCKING = frozenset({Severity.critical, Severity.major})


def is_blocking(severity: Severity) -> bool:
    return severity in _BLOCKING


@dataclass(frozen=True)
class Violation:
    rule_id: str
    severity: Severity
    message: str
    fix_hint: str = ""
    span: dict | None = None

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "span": self.span,
        }


@dataclass
class RuleContext:
    """Everything a rule reads. Draft rules use `cv_json` + `ledger`; rendered rules
    additionally use the compiled artifact fields (populated after RENDER)."""

    cv_json: dict
    ledger: list[dict]
    jd_text: str = ""
    role_title: str | None = None
    track: str | None = None
    name: str = ""
    spec: TemplateSpec | None = None  # the resolved template (page_limit etc.)
    # Populated only at the rendered phase (after a real compile).
    tex: str | None = None
    pdf: bytes | None = None
    extracted_text: str = ""      # primary extractor (pypdf)
    extract_a: str = ""           # pypdf
    extract_b: str = ""           # pdfminer
    gate: dict | None = None
    ats_breakdown: dict | None = None
    _structure: dict | None = field(default=None, compare=False, repr=False)

    @property
    def jd_attached(self) -> bool:
        return bool((self.jd_text or "").strip())

    def structure(self) -> dict:
        """Memoized deterministic structure/hygiene review of the cv_json content."""
        if self._structure is None:
            self._structure = intel.structure_review(
                cv_text=ats._cv_text(self.cv_json), cv_json=self.cv_json
            )
        return self._structure


@dataclass(frozen=True)
class Rule:
    id: str  # bucket.name — immutable once referenced by stored runs
    severity: Severity
    phase: Phase
    fix_mode: FixMode
    check: Callable[[RuleContext], Iterable[Violation]]
    weight: float = 1.0
    constraint: str = ""   # injected into the agent prompt (later slices)
    fix_hint: str = ""     # the remedy, fed back verbatim on repair
    applies: Callable[[RuleContext], bool] = field(default=lambda ctx: True, compare=False)


@dataclass
class Registry:
    rules: list[Rule]

    def version(self) -> str:
        """Stable short hash over the rule set's identity + severity + weight + phase.

        Changing a threshold in a rule's body does not change this (config lives in the
        DB by design); adding/removing a rule or reweighting it does."""
        payload = sorted(
            [r.id, r.severity.value, r.phase.value, r.fix_mode.value, r.weight]
            for r in self.rules
        )
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return digest[:12]

    def for_phase(self, phase: Phase) -> list[Rule]:
        return [r for r in self.rules if r.phase is phase]

    def fix_mode_of(self, rule_id: str) -> FixMode | None:
        return next((r.fix_mode for r in self.rules if r.id == rule_id), None)

    def run(self, ctx: RuleContext, phase: Phase) -> list[Violation]:
        out: list[Violation] = []
        for rule in self.for_phase(phase):
            if not rule.applies(ctx):
                continue
            out.extend(rule.check(ctx))
        return out

    def constraints_block(self, ctx: RuleContext, phase: Phase = Phase.draft) -> str:
        """The applicable rules' constraints, one per line — the agent prompt seed
        (unused until the repair slice; kept here so there is one source of truth)."""
        lines = [
            f"- {r.constraint}"
            for r in self.for_phase(phase)
            if r.constraint and r.applies(ctx)
        ]
        return "\n".join(lines)

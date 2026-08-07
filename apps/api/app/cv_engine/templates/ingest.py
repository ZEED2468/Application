"""Ingest an uploaded custom .tex into a validated TemplateSpec (or reject with reasons).

Untrusted input with its own mini-pipeline: safety → marker/reachability parse → slot
manifest → validate (dummy render → compile → gate). Rejected at save with a specific
reason, never lazily at render.
"""

from __future__ import annotations

from app.core.errors import DomainError
from app.cv_engine.templates.render import KNOWN_MARKERS, find_markers
from app.cv_engine.templates.spec import Slot, TemplateSpec
from app.cv_engine.templates.validate import validate_template
from app.pipelines.apply.latex_safety import assert_safe

_MARKER_TO_SLOT = {
    "SUMMARY": "summary", "SKILLS": "skills", "EXPERIENCE": "experience",
    "PROJECTS": "projects", "EDUCATION": "education",
    "CERTIFICATIONS": "certifications", "LANGUAGES": "languages",
    "CONTACT": "contact", "HEADER": "contact",
}
_REQUIRED = ("summary", "skills", "experience")  # slot ids a complete custom CV must fill


def _slots_from_markers(markers: set[str]) -> tuple[Slot, ...]:
    slots: list[Slot] = []
    seen: set[str] = set()
    for m in markers:
        sid = _MARKER_TO_SLOT.get(m)
        if not sid or sid in seen:
            continue
        seen.add(sid)
        required = sid in _REQUIRED or sid == "contact"
        slots.append(Slot(sid, "custom", required=required,
                          absence_ok="ask" if required else "omit"))
    return tuple(slots)


async def ingest_tex_template(
    tex: str, *, template_id: str, track: str | None, name: str, version: int = 1,
) -> tuple[TemplateSpec, dict]:
    """Validate an uploaded .tex → (TemplateSpec, gate), or raise DomainError(400)."""
    assert_safe(tex)  # forbidden LaTeX primitives → DomainError

    markers = find_markers(tex)
    unknown = markers - KNOWN_MARKERS
    if unknown:
        raise DomainError(
            "Unknown template markers: " + ", ".join(sorted(f"%%CV:{m}%%" for m in unknown))
            + ". Use only the documented %%CV:<SLOT>%% markers.",
            code="template_bad_markers", title="Unrecognized markers",
        )

    missing: list[str] = []
    for m in ("SUMMARY", "SKILLS", "EXPERIENCE"):
        if m not in markers:
            missing.append(f"%%CV:{m}%%")
    if "NAME" not in markers and "HEADER" not in markers:
        missing.append("%%CV:NAME%% or %%CV:HEADER%%")
    if "CONTACT" not in markers and "HEADER" not in markers:
        missing.append("%%CV:CONTACT%% or %%CV:HEADER%%")
    if missing:
        raise DomainError(
            "Template is missing required sections: " + ", ".join(missing) + ".",
            code="template_missing_slots", title="Missing required sections",
        )

    spec = TemplateSpec(
        id=template_id, version=version, name=name, kind="latex", track=track,
        latex=tex, slots=_slots_from_markers(markers), registry_overrides={"page_limit": 2},
    )
    report = await validate_template(spec)
    if not report["ok"]:
        raise DomainError(
            "This template didn't pass validation: " + "; ".join(report["reasons"]) + ".",
            code="template_invalid", title="Template won't render cleanly",
        )
    return spec, report["gate"]

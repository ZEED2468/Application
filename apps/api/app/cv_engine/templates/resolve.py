"""Binding by reference — the ONE template resolver.

Resolution order: a run's explicit `ref` → the track's bound template
(`master_profile.template_id`, which may point at a built-in id or a custom `cv_template`
row) → the canonical default. `get_template` fetches the EXACT pinned template so a stored
run always re-renders identically (custom rows are immutable, keyed by id).

Model imports are lazy (inside the functions) so importing the templates package never
pulls in the app.models registry — that would form an import cycle (models → this package).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from app.core.enums import Track
from app.cv_engine.templates.library import BUILTINS, default_template
from app.cv_engine.templates.spec import Slot, TemplateSpec

if TYPE_CHECKING:
    from app.cv_engine.templates.models import CvTemplate


def _spec_from_row(row: CvTemplate) -> TemplateSpec:
    return TemplateSpec(
        id=str(row.id), version=row.version, name=row.name, kind=row.kind, track=row.track,
        slots=tuple(Slot.from_dict(s) for s in (row.slots or [])),
        registry_overrides=row.registry_overrides or {}, latex=row.latex,
    )


async def get_template(
    session, template_id: str | None, version: int | None = None
) -> TemplateSpec | None:
    """Fetch the exact template by id, or None if unknown."""
    if template_id and template_id in BUILTINS:
        return BUILTINS[template_id]
    if not template_id or session is None:
        return None
    try:
        tid = UUID(template_id)
    except (ValueError, TypeError):
        return None
    from app.cv_engine.templates.models import CvTemplate  # lazy — avoids the model import cycle
    row = (await session.execute(
        select(CvTemplate).where(CvTemplate.id == tid)
    )).scalar_one_or_none()
    return _spec_from_row(row) if row else None


async def resolve_template(
    session, *, user_id, track: str | None, ref: str | None = None
) -> TemplateSpec:
    if ref:
        spec = await get_template(session, ref)
        if spec is not None:
            return spec
    if session is not None and user_id is not None and track:
        try:
            track_enum = Track(track)
        except ValueError:
            track_enum = None
        if track_enum is not None:
            from app.models.master_profile import MasterProfile  # lazy — avoids the cycle
            profile = (await session.execute(
                select(MasterProfile).where(
                    MasterProfile.user_id == user_id, MasterProfile.track == track_enum
                )
            )).scalar_one_or_none()
            if profile and profile.template_id:
                spec = await get_template(session, profile.template_id)
                if spec is not None:
                    return spec
    return default_template()

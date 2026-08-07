"""Templates — the mold, formalized (TemplateSpec + slot manifest + resolution).

A template is a parameterization of the canonical single-column system: a slot manifest
(its demand), registry overrides (policy, e.g. page limit), and a renderer (the canonical
build_tex, or a validated custom .tex with %%CV:<slot>%% markers). Binding is by reference —
one resolver (run → track binding → canonical default), pinned per run — so template
evolution never silently rewrites an old run and no second code path forgets the template.
"""

from app.cv_engine.templates.library import BUILTINS, default_template
from app.cv_engine.templates.render import render_template
from app.cv_engine.templates.resolve import get_template, resolve_template
from app.cv_engine.templates.spec import Slot, TemplateSpec

__all__ = [
    "BUILTINS",
    "Slot",
    "TemplateSpec",
    "default_template",
    "get_template",
    "render_template",
    "resolve_template",
]

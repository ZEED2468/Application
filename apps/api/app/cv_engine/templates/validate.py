"""Save-time template validation — render dummy content, compile, gate + reachability.

Reuses the same primitive as the existing template gate (`render_pdf_checked` +
`format_gate.evaluate`): a template is valid only if it renders realistic content into a
single-column, ATS-parseable PDF, with every marker known. A built-in self-test asserts
every BUILTIN validates; custom .tex uploads run through the same function.
"""

from __future__ import annotations

import shutil

from app.cv_engine.templates.render import KNOWN_MARKERS, find_markers, render_template
from app.cv_engine.templates.spec import TemplateSpec
from app.pipelines.apply import format_gate
from app.pipelines.apply.render import render_pdf_checked

DUMMY_CV = {
    "headline": "Senior Engineer",
    "summary": "Experienced engineer who builds reliable systems in Python and Go.",
    "skills": ["Python", "Go", "Postgres", "Docker"],
    "experience": [{
        "title": "Senior Engineer", "company": "Sample Co", "dates": "2020 -- 2024",
        "bullets": ["Built and shipped production services", "Improved reliability and latency"],
    }],
    "projects": [{"name": "Sample Project", "description": "A small open-source tool."}],
    "education": [{"degree": "BSc Computer Science", "school": "Sample University",
                   "dates": "2014 -- 2018"}],
    "links": {"email": "sample@example.com", "github": "https://github.com/sample"},
}


async def validate_template(spec: TemplateSpec) -> dict:
    """Return {ok, gate, reasons}. `ok` is False on unknown markers or a failed compile;
    a missing compiler leaves the gate `unevaluated` (not a failure)."""
    reasons: list[str] = []
    if spec.kind == "latex":
        unknown = find_markers(spec.latex or "") - KNOWN_MARKERS
        if unknown:
            reasons.append("unknown markers: " + ", ".join(sorted(unknown)))

    tex = render_template(spec, DUMMY_CV, name="Sample Name")
    has_compiler = shutil.which("tectonic") is not None
    pdf, _stderr = await render_pdf_checked(tex)
    gate = format_gate.evaluate(tex=tex, pdf=pdf, has_compiler=has_compiler)
    if gate["status"] == "fail":
        reasons.extend(gate.get("reasons") or ["the template did not compile"])

    return {"ok": not reasons, "gate": gate, "reasons": reasons}

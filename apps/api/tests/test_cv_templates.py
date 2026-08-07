"""TemplateSpec framework — render identity, built-in self-test, custom .tex ingestion.

The canonical/built-in specs must render byte-identically to build_tex (so the golden
fixtures stay green); every built-in must validate; a custom .tex is accepted only when
it's safe, uses known markers, has the required slots, and compiles single-column.
"""

import pytest

from app.core.errors import DomainError
from app.cv_engine.templates import BUILTINS, default_template, render_template
from app.cv_engine.templates.ingest import ingest_tex_template
from app.cv_engine.templates.render import find_markers
from app.cv_engine.templates.validate import validate_template
from app.pipelines.apply.render import build_tex

SAMPLE_CV = {
    "summary": "Backend engineer.", "skills": ["Go", "Kubernetes"],
    "experience": [{"title": "Eng", "company": "Acme", "dates": "2020 -- 2024",
                    "bullets": ["Built things"]}],
    "links": {"github": "https://github.com/x"},
}

_GOOD_TEX = (
    r"\documentclass{article}\usepackage[margin=0.9in]{geometry}\begin{document}"
    "\n%%CV:HEADER%%\n%%CV:SUMMARY%%\n%%CV:SKILLS%%\n%%CV:EXPERIENCE%%\n"
    r"\end{document}"
)


def test_builtins_render_identically_to_build_tex():
    # All built-ins share the canonical mold → byte-identical output → fixtures stay green.
    for spec in BUILTINS.values():
        assert render_template(spec, SAMPLE_CV, name="Ada") == build_tex(SAMPLE_CV, name="Ada")


def test_builtin_page_limits():
    assert default_template().id == "canonical"
    assert {k: v.page_limit for k, v in BUILTINS.items()} == {
        "canonical": 2, "compact": 1, "academic": 5
    }


async def test_every_builtin_validates():
    for tid, spec in BUILTINS.items():
        report = await validate_template(spec)
        # A missing compiler leaves the gate unevaluated (not a failure); with tectonic it passes.
        assert report["ok"], f"built-in {tid} failed validation: {report['reasons']}"
        assert report["gate"]["status"] in ("pass", "unevaluated")


async def test_custom_tex_ingests_and_renders():
    spec, gate = await ingest_tex_template(
        _GOOD_TEX, template_id="t1", track="backend", name="Mine"
    )
    assert spec.kind == "latex" and gate["status"] in ("pass", "unevaluated")
    assert {"summary", "skills", "experience", "contact"} <= {s.id for s in spec.slots}
    tex = render_template(spec, SAMPLE_CV, name="Ada Hunter")
    assert "Ada Hunter" in tex and "Backend engineer" in tex and "Acme" in tex
    assert not find_markers(tex)  # every marker was substituted


@pytest.mark.parametrize(
    "bad,code",
    [
        (r"\input{/etc/passwd} %%CV:HEADER%% %%CV:SUMMARY%% %%CV:SKILLS%% %%CV:EXPERIENCE%%", None),
        (r"\documentclass{article}\begin{document}%%CV:SUMMARY%%\end{document}",
         "template_missing_slots"),
        (r"\documentclass{article}\begin{document}%%CV:FOO%% %%CV:HEADER%% %%CV:SUMMARY%% "
         r"%%CV:SKILLS%% %%CV:EXPERIENCE%%\end{document}", "template_bad_markers"),
    ],
)
async def test_custom_tex_rejections(bad, code):
    with pytest.raises(DomainError) as exc:
        await ingest_tex_template(bad, template_id="t", track=None, name="x")
    if code:
        assert exc.value.code == code

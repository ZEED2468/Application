"""Render a TemplateSpec + cv_json → .tex.

Canonical/built-in specs render via the UNTOUCHED `build_tex` (so the golden fixtures stay
byte-identical). A custom `.tex` template injects per-slot LaTeX bodies at `%%CV:<SLOT>%%`
markers — the per-slot renderers mirror build_tex's section output (reusing its `_esc` /
`_section`), so a custom template gets the same escaped, ATS-safe content in its own layout.
"""

from __future__ import annotations

import re

from app.cv_engine.templates.spec import TemplateSpec
from app.pipelines.apply.render import _esc, _section, build_tex

# %%CV:SLOT%% marker convention for custom templates.
MARKER_RE = re.compile(r"%%CV:([A-Z]+)%%")
KNOWN_MARKERS = {
    "NAME", "HEADER", "CONTACT", "SUMMARY", "SKILLS", "EXPERIENCE",
    "PROJECTS", "EDUCATION", "CERTIFICATIONS", "LANGUAGES",
}
# Markers a complete custom template must contain (map onto the canonical required slots).
REQUIRED_MARKERS = {"NAME", "SUMMARY", "SKILLS", "EXPERIENCE"}


def render_template(spec: TemplateSpec, cv_json: dict, *, name: str) -> str:
    if spec.kind == "latex" and spec.latex:
        return render_latex_template(spec.latex, cv_json, name=name)
    # All built-ins share the canonical ATS-safe mold.
    return build_tex(cv_json, name=name)


def find_markers(tex: str) -> set[str]:
    return set(MARKER_RE.findall(tex or ""))


def render_latex_template(latex: str, cv_json: dict, *, name: str) -> str:
    bodies = {
        "NAME": _name_body(name),
        "HEADER": _header_body(cv_json, name),
        "CONTACT": _contact_body(cv_json),
        "SUMMARY": _summary_body(cv_json),
        "SKILLS": _skills_body(cv_json),
        "EXPERIENCE": _experience_body(cv_json),
        "PROJECTS": _projects_body(cv_json),
        "EDUCATION": _education_body(cv_json),
        "CERTIFICATIONS": _certifications_body(cv_json),
        "LANGUAGES": _languages_body(cv_json),
    }
    out = latex
    for slot, body in bodies.items():
        out = out.replace(f"%%CV:{slot}%%", body)
    return out


# --- Per-slot LaTeX bodies (mirror build_tex's section output) -----------------------


def _name_body(name: str) -> str:
    return rf"\begin{{center}}{{\LARGE\bfseries {_esc(name)}}}\end{{center}}"


def _contact_body(cv_json: dict) -> str:
    contacts = [str(v) for v in (cv_json.get("links") or {}).values() if v]
    if not contacts:
        return ""
    return rf"\begin{{center}}\small {_esc('  |  '.join(contacts))}\end{{center}}"


def _header_body(cv_json: dict, name: str) -> str:
    parts = [_name_body(name)]
    if cv_json.get("headline"):
        parts.append(rf"\begin{{center}}{_esc(cv_json['headline'])}\end{{center}}")
    contact = _contact_body(cv_json)
    if contact:
        parts.append(contact)
    return "\n".join(parts)


def _summary_body(cv_json: dict) -> str:
    if not cv_json.get("summary"):
        return ""
    return _section("Summary") + "\n" + _esc(cv_json["summary"])


def _skills_body(cv_json: dict) -> str:
    skills = cv_json.get("skills") or []
    if not skills:
        return ""
    return _section("Skills") + "\n" + _esc(", ".join(str(s) for s in skills))


def _experience_body(cv_json: dict) -> str:
    experience = cv_json.get("experience") or []
    if not experience:
        return ""
    lines = [_section("Experience")]
    for e in experience:
        title = " --- ".join(filter(None, [e.get("title") or e.get("role"), e.get("company")]))
        dates = e.get("dates") or " -- ".join(filter(None, [e.get("start"), e.get("end")]))
        header = rf"\textbf{{{_esc(title)}}}"
        if dates:
            header += rf"\hfill {_esc(dates)}"
        lines.append(header + r"\\[2pt]")
        bullets = e.get("bullets") or []
        if bullets:
            lines.append(r"\begin{itemize}")
            lines += [rf"\item {_esc(b)}" for b in bullets]
            lines.append(r"\end{itemize}")
    return "\n".join(lines)


def _projects_body(cv_json: dict) -> str:
    projects = cv_json.get("projects") or []
    if not projects:
        return ""
    lines = [_section("Projects")]
    for p in projects:
        head = rf"\textbf{{{_esc(p.get('name') or '')}}}"
        desc = p.get("description")
        lines.append(head + (rf": {_esc(desc)}" if desc else "") + r"\\[3pt]")
    return "\n".join(lines)


def _education_body(cv_json: dict) -> str:
    education = cv_json.get("education") or []
    if not education:
        return ""
    lines = [_section("Education")]
    for ed in education:
        if isinstance(ed, str):
            lines.append(_esc(ed) + r"\\[2pt]")
            continue
        deg = " --- ".join(filter(None, [ed.get("degree"),
                                         ed.get("school") or ed.get("institution")]))
        dates = ed.get("dates") or " -- ".join(filter(None, [ed.get("start"), ed.get("end")]))
        row = rf"\textbf{{{_esc(deg)}}}"
        if dates:
            row += rf"\hfill {_esc(dates)}"
        lines.append(row + r"\\[2pt]")
    return "\n".join(lines)


def _certifications_body(cv_json: dict) -> str:
    certs = cv_json.get("certifications") or []
    if not certs:
        return ""
    lines = [_section("Certifications"), r"\begin{itemize}"]
    lines += [rf"\item {_esc(c)}" for c in certs]
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def _languages_body(cv_json: dict) -> str:
    languages = cv_json.get("languages") or []
    if not languages:
        return ""
    return _section("Languages") + "\n" + _esc(", ".join(str(x) for x in languages))

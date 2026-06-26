"""Regenerate a tailored CV / cover letter in the hunter's own LaTeX template.

The model is given the uploaded `.tex` as a literal skeleton to preserve and the
ALREADY-VETTED tailored content (`tailoring.tailor`'s `cv_json` / the truth-bounded
3-paragraph cover body) as the only facts it may use — so this looser free-form
LaTeX channel can reformat vetted content but has nothing to fabricate from. ATS
recommendations enter only as "emphasise if genuinely supported" guidance.

Every path is compile-safe: the LLM output is sanitised and compiled in `--untrusted`
mode; if it will not compile (or there's no template / no LLM), we fall back to the
deterministic `build_tex` / `build_cover_letter_tex`, which is always renderable.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import structlog

from app.llm import client, tailoring
from app.pipelines.apply import render
from app.pipelines.apply.latex_safety import sanitize_latex

log = structlog.get_logger(__name__)

# Reuse the SAME model the ATS checker uses (the `ats_analyze` feature) — no separate
# LaTeX model to configure. It runs through the standard provider facade, so whatever
# provider/model/key/base_url powers ATS scoring (anthropic | openai-compatible |
# google) also powers the rewrite. Output budgets stay model-safe so small models work
# too (Haiku/Gemini-flash cap output near ~4k); override via env if needed.
_FEATURE = "ats_analyze"
_CV_MAX_TOKENS = 4000
_COVER_MAX_TOKENS = 1500


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v.strip()) if v and v.strip().isdigit() else default


@dataclass(slots=True)
class RegenResult:
    latex: str
    pdf: bytes | None
    compiled: bool
    fell_back: str | None  # None when the LLM rewrite succeeded; else the reason
    stderr: str | None


def _strip_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:la)?tex?\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    return s


_CV_SYSTEM = (
    "You rewrite a LaTeX CV. You are given a LaTeX TEMPLATE that is the literal "
    "skeleton: preserve its \\documentclass, packages, layout, and section commands "
    "EXACTLY — only swap in the tailored content provided.\n"
    "STRICT TRUTH RULE: use ONLY facts present in TAILORED_CONTENT (already vetted). "
    "Never invent employers, dates, skills, metrics, or achievements.\n"
    "ATS: weave in the ATS recommendations and priority technologies ONLY where "
    "TAILORED_CONTENT genuinely supports them; never claim a skill it does not show.\n"
    "SAFETY: output a single complete LaTeX document. Do NOT use \\write18, \\input, "
    "\\include, \\immediate, shell-escape, or any file/IO/shell primitive.\n"
    "Return ONLY the .tex source — no prose, no code fences."
)

_COVER_SYSTEM = (
    "You rewrite a LaTeX cover letter. You are given a LaTeX TEMPLATE that is the "
    "literal skeleton: preserve its \\documentclass, packages, and layout EXACTLY — "
    "only place the provided letter body into it.\n"
    "STRICT TRUTH RULE: use ONLY the provided LETTER_BODY text; do not add claims.\n"
    "SAFETY: output a single complete LaTeX document. Do NOT use \\write18, \\input, "
    "\\include, \\immediate, shell-escape, or any file/IO/shell primitive.\n"
    "Return ONLY the .tex source — no prose, no code fences."
)


def _cv_prompt(*, template_tex, cv_json, owner_name, job_title, priority_techs, ats_recs) -> str:
    recs = ats_recs or {}
    return (
        f"TEMPLATE (skeleton to preserve):\n{template_tex}\n\n"
        f"TAILORED_CONTENT (only allowed facts, JSON):\n{json.dumps(cv_json)}\n\n"
        f"CANDIDATE NAME: {owner_name}\n"
        f"ROLE: {job_title}\n"
        f"PRIORITY TECHNOLOGIES: {', '.join(priority_techs or [])}\n"
        f"ATS MISSING-CRITICAL: {', '.join(recs.get('missing_critical') or [])}\n"
        f"ATS GAPS: {', '.join(recs.get('gaps') or [])}\n"
        f"ATS RECOMMENDATIONS: {' | '.join(recs.get('ai_recommendations') or [])}\n\n"
        "Return only the .tex source."
    )


def _cover_prompt(*, template_tex, cl_body, owner_name, company, role_title) -> str:
    return (
        f"TEMPLATE (skeleton to preserve):\n{template_tex}\n\n"
        f"LETTER_BODY (the only allowed text):\n{cl_body}\n\n"
        f"CANDIDATE NAME: {owner_name}\nCOMPANY: {company}\nROLE: {role_title}\n\n"
        "Return only the .tex source."
    )


async def _regen(*, template_tex, system, prompt, max_tokens, fallback_tex) -> RegenResult:
    """Try the LLM rewrite of `template_tex` (using the shared ATS model); fall back to
    `fallback_tex` (always compilable) on no template / no LLM / empty / non-compiling
    output."""
    fell_back: str | None
    stderr: str | None = None
    has_template = bool(template_tex and template_tex.strip())

    if has_template and client.is_live(_FEATURE):
        try:
            raw = await client.complete_text(
                system, prompt, max_tokens=max_tokens, feature=_FEATURE
            )
            tex = sanitize_latex(_strip_fences(raw)).strip()
            if tex:
                pdf, err = await render.render_pdf_checked(tex)
                if pdf is not None:
                    return RegenResult(latex=tex, pdf=pdf, compiled=True, fell_back=None, stderr=None)
                fell_back, stderr = "no_compile", err
            else:
                fell_back = "empty_output"
        except Exception as exc:  # noqa: BLE001 — never break regeneration
            log.warning("latex_regen.llm_failed", feature=_FEATURE,
                        error=str(exc), exc_type=type(exc).__name__)
            fell_back = "llm_failed"
    elif not has_template:
        fell_back = "no_template"
    else:
        fell_back = "no_llm"

    pdf = await render.render_pdf(fallback_tex)
    return RegenResult(latex=fallback_tex, pdf=pdf, compiled=True, fell_back=fell_back, stderr=stderr)


async def regenerate_cv_latex(
    *, template_tex: str | None, profile_dict: dict, owner_name: str,
    job_title: str, jd_text: str | None, ats_recs: dict | None,
    priority_techs: list[str] | None,
) -> RegenResult:
    """Tailor (truth-bounded) then render the result into the user's CV skeleton."""
    cv_json, _diff = await tailoring.tailor(
        profile_dict, job_title=job_title, job_description=jd_text,
        priority_techs=priority_techs,
    )
    prompt = _cv_prompt(
        template_tex=template_tex, cv_json=cv_json, owner_name=owner_name,
        job_title=job_title, priority_techs=priority_techs, ats_recs=ats_recs,
    )
    fallback_tex = render.build_tex(cv_json, name=owner_name)
    return await _regen(
        template_tex=template_tex, system=_CV_SYSTEM, prompt=prompt,
        max_tokens=_env_int("LLM_LATEX_CV_MAX_TOKENS", _CV_MAX_TOKENS),
        fallback_tex=fallback_tex,
    )


async def regenerate_cover_latex(
    *, template_tex: str | None, cl_body: str, owner_name: str,
    company: str, role_title: str,
) -> RegenResult:
    """Render the truth-bounded 3-paragraph body into the user's cover skeleton."""
    prompt = _cover_prompt(
        template_tex=template_tex, cl_body=cl_body, owner_name=owner_name,
        company=company, role_title=role_title,
    )
    fallback_tex = render.build_cover_letter_tex(cl_body, name=owner_name)
    return await _regen(
        template_tex=template_tex, system=_COVER_SYSTEM, prompt=prompt,
        max_tokens=_env_int("LLM_LATEX_COVER_MAX_TOKENS", _COVER_MAX_TOKENS),
        fallback_tex=fallback_tex,
    )

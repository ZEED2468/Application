"""AI layer for the global ATS checker — full CV vs JD analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.pipelines.apply import ats


@dataclass(slots=True)
class AiGap:
    skill: str
    severity: str
    reason: str


@dataclass(slots=True)
class AtsAiAnalysis:
    fit_score: float | None
    fit_summary: str
    strengths: list[str] = field(default_factory=list)
    gaps: list[AiGap] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    false_positives: list[str] = field(default_factory=list)
    verdict: str = ""


def _offline_analysis(
    *,
    cv_text: str,
    jd_text: str,
    role_title: str,
    rule_score: float,
    breakdown: dict,
) -> AtsAiAnalysis:
    matched = breakdown.get("matched_keywords") or []
    missing = ats.gap_skills(breakdown, limit=8)
    gaps = [
        AiGap(skill=g, severity="medium", reason="Flagged by rule-based keyword scan.")
        for g in missing
    ]
    verdict = (
        "Strong fit" if rule_score >= 75
        else "Moderate fit" if rule_score >= 50
        else "Weak fit"
    )
    recs: list[str] = []
    if missing:
        recs.append(
            f"Address missing terms where truthful: {', '.join(missing[:5])}."
        )
    if rule_score < 70:
        recs.append("Mirror JD language in skills and bullet points where accurate.")
    return AtsAiAnalysis(
        fit_score=rule_score,
        fit_summary=(
            "Offline analysis from keyword coverage only. "
            "Configure an LLM for deeper CV-vs-JD review."
        ),
        strengths=[f"Matched: {k}" for k in matched[:8]],
        gaps=gaps,
        recommendations=recs,
        false_positives=[],
        verdict=verdict,
    )


def _parse_ai_response(raw: str, *, rule_score: float) -> AtsAiAnalysis:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)

    gaps: list[AiGap] = []
    for item in data.get("gaps") or []:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or "").strip()
        if not skill:
            continue
        gaps.append(
            AiGap(
                skill=skill,
                severity=str(item.get("severity") or "medium").strip(),
                reason=str(item.get("reason") or "").strip(),
            )
        )

    fit = data.get("fit_score")
    try:
        fit_score = float(fit) if fit is not None else rule_score
    except (TypeError, ValueError):
        fit_score = rule_score

    return AtsAiAnalysis(
        fit_score=min(100.0, max(0.0, fit_score)),
        fit_summary=str(data.get("fit_summary") or "").strip(),
        strengths=[str(s).strip() for s in (data.get("strengths") or []) if str(s).strip()],
        gaps=gaps[:10],
        recommendations=[
            str(r).strip() for r in (data.get("recommendations") or []) if str(r).strip()
        ],
        false_positives=[
            str(x).strip() for x in (data.get("false_positives") or []) if str(x).strip()
        ],
        verdict=str(data.get("verdict") or "").strip(),
    )


async def analyze(
    *,
    cv_text: str,
    jd_text: str,
    role_title: str,
    rule_score: float,
    breakdown: dict,
) -> AtsAiAnalysis:
    from app.llm import client

    if not client.is_live("ats_analyze"):
        return _offline_analysis(
            cv_text=cv_text,
            jd_text=jd_text,
            role_title=role_title,
            rule_score=rule_score,
            breakdown=breakdown,
        )

    system = (
        "You are an expert ATS-style resume reviewer. Compare ONE candidate CV against "
        "ONE job description. Return JSON ONLY with keys: "
        "fit_score (0-100 number), fit_summary (string), strengths (string array), "
        "gaps (array of {skill, severity: high|medium|low, reason}), "
        "recommendations (string array), false_positives (rule-based keywords that are "
        "NOT real gaps), verdict (one of: Strong fit | Moderate fit | Weak fit | Poor fit). "
        "Be truthful: only cite skills evidenced in the CV. Do not invent experience. "
        "Distinguish Java vs JavaScript, MySQL vs PostgreSQL, etc."
    )
    prompt = json.dumps(
        {
            "role_title": role_title,
            "job_description": jd_text,
            "cv_text": cv_text[:12000],
            "rule_based_score": rule_score,
            "rule_based_matched": breakdown.get("matched_keywords") or [],
            "rule_based_missing": breakdown.get("missing_keywords") or [],
        },
        indent=2,
    )
    raw = await client.try_complete_text(system, prompt, max_tokens=2000, feature="ats_analyze")
    if raw is None:
        return _offline_analysis(
            cv_text=cv_text,
            jd_text=jd_text,
            role_title=role_title,
            rule_score=rule_score,
            breakdown=breakdown,
        )
    try:
        return _parse_ai_response(raw, rule_score=rule_score)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return _offline_analysis(
            cv_text=cv_text,
            jd_text=jd_text,
            role_title=role_title,
            rule_score=rule_score,
            breakdown=breakdown,
        )


def analysis_to_dict(analysis: AtsAiAnalysis) -> dict:
    return {
        "fit_score": analysis.fit_score,
        "fit_summary": analysis.fit_summary,
        "strengths": analysis.strengths,
        "gaps": [
            {"skill": g.skill, "severity": g.severity, "reason": g.reason}
            for g in analysis.gaps
        ],
        "recommendations": analysis.recommendations,
        "false_positives": analysis.false_positives,
        "verdict": analysis.verdict,
    }

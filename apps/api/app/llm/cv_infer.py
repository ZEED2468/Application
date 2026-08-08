"""Slot inference — compose a missing, DERIVABLE slot from the ledger, truth-bounded + verified.

Slice 7's INFERABLE path. The one inferable required slot is the summary: a restatement of the
facts the candidate already gave (experience + skills), never a new fact. Mirrors the cv_repair/
cv_judge facade — gate on `client.is_live`, `try_complete_text`, tolerant parse, `None` -> no-op.

The module NEVER decides safety itself: it proposes a summary; the engine keeps it only if it
clears BOTH the deterministic grounding seal (re-diagnose — no invented number/entity) AND this
module's independent `supports` verifier. Offline (fake mode) every call is a no-op, so a missing
summary simply surfaces downstream as today.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

PROMPT_VERSION = "cv_infer.v1"


@dataclass
class InferResult:
    summary: str | None = None
    model: str | None = None
    applied: bool = False


def _parse_json(raw: str) -> dict:
    """Extract the outermost JSON object (tolerates ```json fences / surrounding prose)."""
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if not m:
        raise ValueError("no JSON object in completion")
    return json.loads(m.group(0))


def _model(feature: str) -> str | None:
    from app.llm import config as llm_config
    return llm_config.resolve(feature).model


def _facts_of(ledger: list[dict], kinds: tuple[str, ...]) -> list[str]:
    return [str(f.get("text") or "").strip()
            for f in (ledger or [])
            if f.get("kind") in kinds and str(f.get("text") or "").strip()]


async def infer_summary(
    ledger: list[dict], *, role_title: str | None = None, jd_text: str = ""
) -> InferResult:
    """Compose a 2-3 line summary from the ledger's role + skill facts (no-op offline/on error)."""
    from app.llm import client

    if not client.is_live("cv_infer"):
        return InferResult(applied=False)
    roles = _facts_of(ledger, ("role",))
    skills = _facts_of(ledger, ("skill",))
    if not roles:                       # nothing to restate -> a true gap, not inferable
        return InferResult(applied=False)

    system = (
        "You write a CV professional summary by RESTATING the candidate's own history — never "
        "inventing. Compose 2-3 lines using ONLY the roles and skills provided: no new employer, "
        "metric, title, or claim, and no number that is not already there. If the material is too "
        "thin to summarize truthfully, return an empty string. Return JSON ONLY: "
        "{\"summary\": string}."
    )
    prompt = json.dumps({
        "roles": roles,
        "skills": skills,
        "role_title": role_title or "",
        "job_description": jd_text[:1500],
    }, indent=2)

    raw = await client.try_complete_text(system, prompt, max_tokens=400, feature="cv_infer")
    if raw is None:
        return InferResult(applied=False)
    try:
        summary = str(_parse_json(raw).get("summary") or "").strip()
    except (ValueError, json.JSONDecodeError):
        return InferResult(applied=False)
    if not summary:
        return InferResult(applied=False)
    return InferResult(summary=summary, model=_model("cv_infer"), applied=True)


async def supports(summary: str, ledger_text: str) -> bool:
    """Independent verifier (door #2): is the summary fully supported by the candidate's history?

    Sees only the summary + the ledger text. Biased to false-negatives — no verifier configured, a
    failure, or an unsure answer all mean NOT supported (the inferred summary is dropped)."""
    if not str(summary).strip():
        return False
    from app.llm import client

    if not client.is_live("cv_infer_verify"):
        return False
    system = (
        "You are a strict fact-checker. The SUMMARY is SUPPORTED only if every claim, number, "
        "employer, title, and skill in it is present in the candidate's HISTORY (rewording is "
        "fine). If it adds anything not in the history, or you are unsure, it is NOT supported. "
        "Answer JSON ONLY: {\"supported\": true|false}."
    )
    prompt = json.dumps({"summary": summary, "history": ledger_text[:6000]})
    raw = await client.try_complete_text(system, prompt, max_tokens=80, feature="cv_infer_verify")
    if raw is None:
        return False
    try:
        return _parse_json(raw).get("supported") is True
    except (ValueError, json.JSONDecodeError):
        return False

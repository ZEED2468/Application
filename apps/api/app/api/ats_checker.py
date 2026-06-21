"""Global ATS checker — any CV text/file against any JD."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.deps import current_principal
from app.llm import ats_analyze
from app.pipelines.apply import ats
from app.pipelines.apply.cv_parse import cv_json_from_text, extract_text_from_bytes

router = APIRouter(prefix="/ats", tags=["ats"])


def _default_role_title(jd_text: str) -> str:
    for line in (jd_text or "").splitlines():
        line = line.strip()
        if line:
            return line[:120]
    return "Role"


class AtsCheckJsonRequest(BaseModel):
    jd_text: str
    cv_text: str
    role_title: str | None = None
    use_ai: bool = True


@router.post("/check")
async def check_ats_multipart(
    jd_text: str = Form(...),
    role_title: str | None = Form(default=None),
    cv_text: str | None = Form(default=None),
    use_ai: bool = Form(default=True),
    file: UploadFile | None = File(default=None),
    _principal=Depends(current_principal),
) -> dict:
    """Compare an uploaded or pasted CV against a JD (multipart)."""
    filename: str | None = None
    text = (cv_text or "").strip()
    if file is not None and file.filename:
        data = await file.read()
        filename = file.filename
        extracted = extract_text_from_bytes(file.filename, data).strip()
        if extracted:
            text = extracted
    if len(text) < 20:
        from app.core.errors import DomainError

        raise DomainError("Provide CV text or upload a PDF/DOCX with readable content.")
    if len(jd_text.strip()) < 20:
        from app.core.errors import DomainError

        raise DomainError("Job description is too short.")

    return await _run_check(
        jd_text=jd_text.strip(),
        cv_text=text,
        role_title=(role_title or "").strip() or _default_role_title(jd_text),
        use_ai=use_ai,
        cv_filename=filename,
    )


@router.post("/check/json")
async def check_ats_json(
    body: AtsCheckJsonRequest,
    _principal=Depends(current_principal),
) -> dict:
    """Compare pasted CV + JD (JSON body)."""
    if len(body.cv_text.strip()) < 20:
        from app.core.errors import DomainError

        raise DomainError("CV text is too short.")
    if len(body.jd_text.strip()) < 20:
        from app.core.errors import DomainError

        raise DomainError("Job description is too short.")
    return await _run_check(
        jd_text=body.jd_text.strip(),
        cv_text=body.cv_text.strip(),
        role_title=(body.role_title or "").strip() or _default_role_title(body.jd_text),
        use_ai=body.use_ai,
        cv_filename=None,
    )


async def _run_check(
    *,
    jd_text: str,
    cv_text: str,
    role_title: str,
    use_ai: bool,
    cv_filename: str | None,
) -> dict:
    cv_json = cv_json_from_text(cv_text)
    breakdown = ats.score(cv_json=cv_json, jd_text=jd_text, role_title=role_title)
    rule_score = breakdown["score"]

    ai_block: dict | None = None
    if use_ai:
        analysis = await ats_analyze.analyze(
            cv_text=cv_text,
            jd_text=jd_text,
            role_title=role_title,
            rule_score=rule_score,
            breakdown=breakdown,
        )
        ai_block = ats_analyze.analysis_to_dict(analysis)
        from app.llm import client

        ai_block["ai_powered"] = client.is_live("ats_analyze")

    return {
        "role_title": role_title,
        "cv_filename": cv_filename,
        "cv_word_count": len(re.findall(r"\w+", cv_text)),
        "rule_based": {
            "score": rule_score,
            "breakdown": breakdown,
            "gaps": ats.gap_skills(breakdown),
        },
        "ai": ai_block,
    }

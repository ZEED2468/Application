"""CV-engine templates API — list / upload (validate) / bind per track / preview.

Built-in templates + the user's validated custom .tex templates. Binding sets which
template a track uses (`master_profile.template_id`); the engine resolves + pins it.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Track
from app.core.errors import DomainError, NotFoundError
from app.core.ids import new_id
from app.cv_engine.templates import BUILTINS, render_template
from app.cv_engine.templates.ingest import ingest_tex_template
from app.cv_engine.templates.models import CvTemplate
from app.cv_engine.templates.resolve import _spec_from_row
from app.cv_engine.templates.validate import DUMMY_CV
from app.db import get_session
from app.deps import current_user
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.pipelines.apply.render import render_pdf_checked

router = APIRouter(prefix="/cv", tags=["cv"])

_MAX = 512 * 1024  # 512 KB — a .tex template


async def _owned_spec(session, user: User, template_id: str):
    """Resolve a template the user may use: built-ins freely, custom only if they own it."""
    if template_id in BUILTINS:
        return BUILTINS[template_id]
    from uuid import UUID
    try:
        tid = UUID(template_id)
    except (ValueError, TypeError):
        return None
    row = (await session.execute(
        select(CvTemplate).where(CvTemplate.id == tid, CvTemplate.user_id == user.id)
    )).scalar_one_or_none()
    return _spec_from_row(row) if row else None


@router.get("/templates", summary="List available CV templates (built-in + custom)")
async def list_templates(
    track: str | None = None,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    items = [{**spec.summary(), "source": "builtin", "gate": None} for spec in BUILTINS.values()]
    rows = (await session.execute(
        select(CvTemplate).where(CvTemplate.user_id == user.id)
    )).scalars().all()
    items += [{**_spec_from_row(r).summary(), "source": "custom", "gate": r.gate} for r in rows]

    bound = None
    if track:
        try:
            te = Track(track)
        except ValueError:
            te = None
        if te is not None:
            profile = (await session.execute(
                select(MasterProfile).where(
                    MasterProfile.user_id == user.id, MasterProfile.track == te
                )
            )).scalar_one_or_none()
            bound = profile.template_id if profile else None
    return {"templates": items, "bound": bound}


@router.post("/templates/upload", summary="Upload + validate a custom .tex template")
async def upload_template(
    track: str = Form(...), name: str = Form(...), file: UploadFile = File(...),
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".tex", ".txt"}:
        raise DomainError("Upload a .tex template file.", title="Unsupported file type")
    data = await file.read()
    if not data or len(data) > _MAX:
        raise DomainError("Template is empty or too large (max 512 KB).")
    tex = data.decode("utf-8", "replace")

    tid = new_id()
    spec, gate = await ingest_tex_template(  # raises DomainError(400) on reject
        tex, template_id=str(tid), track=track, name=name,
    )
    row = CvTemplate(
        id=tid, user_id=user.id, track=track, name=name, kind="latex", latex=tex,
        slots=[s.to_dict() for s in spec.slots], registry_overrides=spec.registry_overrides,
        gate=gate,
    )
    session.add(row)
    await session.flush()
    return {**spec.summary(), "id": str(row.id), "source": "custom", "gate": gate}


class BindBody(BaseModel):
    track: Track
    template_id: str


@router.post("/templates/bind", summary="Bind a template to a track")
async def bind_template(
    body: BindBody,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if await _owned_spec(session, user, body.template_id) is None:
        raise NotFoundError("Unknown template.")
    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == user.id, MasterProfile.track == body.track
        )
    )).scalar_one_or_none()
    if profile is None:
        raise NotFoundError("Set up this track (upload a CV) before choosing a template.")
    profile.template_id = body.template_id
    await session.flush()
    return {"track": body.track.value, "template_id": body.template_id}


@router.get("/templates/{template_id}/preview", summary="Preview a template with sample content")
async def preview_template(
    template_id: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    spec = await _owned_spec(session, user, template_id)
    if spec is None:
        raise NotFoundError("Unknown template.")
    tex = render_template(spec, DUMMY_CV, name=user.name or "Sample Name")
    pdf, stderr = await render_pdf_checked(tex)
    if not pdf:
        raise DomainError(
            "This template didn't compile: " + (stderr or "unknown error")[:200],
            code="template_invalid", title="Preview failed",
        )
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="template-preview.pdf"'},
    )

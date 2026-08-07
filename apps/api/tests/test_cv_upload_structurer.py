"""Upload structurer (deterministic-primary) — an offline upload yields real structure.

Before Slice 3 an upload with no AI key produced bullets-only, no dates, no contact. The
deterministic parser now runs at the upload seam, so the MasterProfile gets dated
experience + social links + canonical sections with zero LLM.
"""

import io

import docx
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.api.onboarding import upload_role_cv
from app.core.enums import ParseStatus, Track, UserRole
from app.models.master_profile import MasterProfile
from app.models.role_cv import RoleCv
from app.models.user import User
from app.security import hash_password

CV_TEXT = """Ada Hunter
Backend Engineer
ada@example.com  |  linkedin.com/in/adahunter  |  github.com/adahunter

PROFESSIONAL SUMMARY
Backend engineer who builds production systems in Go and Kubernetes.

WORK EXPERIENCE
Senior Backend Engineer — Streamline
Jan 2020 - Present
- Built Go microservices serving many teams across the org
- Reduced infra toil across the whole platform meaningfully

SKILLS
Go, Kubernetes, Postgres, gRPC, Docker

EDUCATION
BSc Computer Science — University of Lagos
2013 - 2017
"""


def _docx_bytes(text: str) -> bytes:
    doc = docx.Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def test_offline_upload_yields_dated_structured_profile(session):
    user = User(email="ada@ex.com", password_hash=hash_password("x"),
                name="Ada Hunter", role=UserRole.hunter)
    session.add(user)
    await session.flush()

    upload = UploadFile(filename="cv.docx", file=io.BytesIO(_docx_bytes(CV_TEXT)))
    result = await upload_role_cv(track=Track.backend, file=upload, user=user, session=session)

    assert result["parse_status"] == "parsed"
    assert result["structured_by"] == "deterministic"
    assert result["confidence"]["experience"] == 1.0

    role_cv = (await session.execute(
        select(RoleCv).where(RoleCv.user_id == user.id, RoleCv.track == Track.backend)
    )).scalar_one()
    assert role_cv.parse_status is ParseStatus.parsed
    assert role_cv.parsed_at is not None  # was dead before Slice 3

    profile = (await session.execute(
        select(MasterProfile).where(
            MasterProfile.user_id == user.id, MasterProfile.track == Track.backend
        )
    )).scalar_one()
    # Real dated experience (not bullets-only) + social links — the Slice-3 win.
    assert profile.experience and profile.experience[0].get("dates")
    assert profile.experience[0].get("title") and profile.experience[0].get("company")
    assert "linkedin" in (profile.links or {}) and "github" in (profile.links or {})
    assert "Go" in profile.skills

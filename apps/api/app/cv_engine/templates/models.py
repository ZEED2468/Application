"""cv_template — a user's validated custom .tex template (immutable, per the spec).

Modeled on the versioned-immutable pattern: each save creates a new row (a new id),
so a run that pinned an older template still resolves + re-renders it identically.
Stores the validated LaTeX + the detected slot manifest + the save-time format gate.
"""

import uuid

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk
from app.models.master_profile import JsonB


class CvTemplate(Base, TimestampMixin):
    __tablename__ = "cv_template"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    track: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="latex", nullable=False)
    latex: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The detected slot manifest (list of Slot dicts) + per-template policy.
    slots: Mapped[list] = mapped_column(JsonB, default=list)
    registry_overrides: Mapped[dict] = mapped_column(JsonB, default=dict)
    # The ATS format gate from the save-time trial compile.
    gate: Mapped[dict | None] = mapped_column(JsonB, nullable=True)

"""latex_template — a per (user, track, kind) LaTeX skeleton.

A hunter uploads their own CV / cover-letter LaTeX as the literal design they want
applications rendered in. The regeneration engine treats `source` as the skeleton to
preserve (layout, packages, section commands) and swaps in truth-bounded tailored
content; `build_tex` is the deterministic fallback when no template is on file.
"""

import uuid

from sqlalchemy import Enum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import LatexKind, Track
from app.db import Base
from app.models.base import TimestampMixin, pk, user_fk


class LatexTemplate(Base, TimestampMixin):
    __tablename__ = "latex_template"
    __table_args__ = (
        UniqueConstraint("user_id", "track", "kind", name="uq_latex_template_user_track_kind"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = user_fk()
    track: Mapped[Track] = mapped_column(Enum(Track, native_enum=False), nullable=False)
    kind: Mapped[LatexKind] = mapped_column(Enum(LatexKind, native_enum=False), nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)  # the raw .tex skeleton
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # R2

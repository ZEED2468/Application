"""cover_letter.latex_source: store the committed cover LaTeX inline

Additive. Adds a nullable Text `latex_source` column to `cover_letter` so the
résumé editor can open the committed cover letter's LaTeX to tweak (mirrors
`generated_cv.latex_source`). No data migration.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cover_letter", sa.Column("latex_source", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cover_letter", "latex_source")

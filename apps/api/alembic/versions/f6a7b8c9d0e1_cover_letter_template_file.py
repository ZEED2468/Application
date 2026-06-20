"""Add source file fields to cover_letter_template."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "cover_letter_template",
        sa.Column("original_filename", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "cover_letter_template",
        sa.Column("source_file_key", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cover_letter_template", "source_file_key")
    op.drop_column("cover_letter_template", "original_filename")

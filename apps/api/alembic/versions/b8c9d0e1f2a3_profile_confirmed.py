"""Track explicit profile confirmation; reset on CV re-upload."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "master_profile",
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        "UPDATE master_profile SET confirmed = true "
        "WHERE truth_corpus IS NOT NULL AND trim(truth_corpus) <> ''"
    )


def downgrade() -> None:
    op.drop_column("master_profile", "confirmed")

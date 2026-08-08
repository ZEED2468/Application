"""cv_engine: cv_template + master_profile.template_id

Additive. Creates the `cv_template` table (validated custom user templates, versioned/
immutable) and adds the per-track binding `master_profile.template_id` (a built-in id or a
cv_template ref; NULL → the canonical default). No existing data to backfill.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "cv_template",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("track", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("kind", sa.String(length=16), server_default="latex", nullable=False),
        sa.Column("latex", sa.Text(), nullable=True),
        sa.Column("slots", JsonB, nullable=True),
        sa.Column("registry_overrides", JsonB, nullable=True),
        sa.Column("gate", JsonB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.add_column("master_profile", sa.Column("template_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("master_profile", "template_id")
    op.drop_table("cv_template")

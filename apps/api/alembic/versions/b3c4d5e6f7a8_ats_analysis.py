"""ats_analysis: persisted, versioned ATS check results

Additive. Creates the `ats_analysis` table so ATS checks are a durable, cross-device,
versioned record instead of a browser sessionStorage handoff. No existing table is
altered; nothing to backfill.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ats_analysis",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id", ondelete="CASCADE"),
                  nullable=True, index=True),
        sa.Column("track", sa.String(length=50), nullable=True),
        sa.Column("role_title", sa.String(length=200), nullable=True),
        sa.Column("gate_status", sa.String(length=16), server_default="unevaluated",
                  nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("breakdown", JsonB, nullable=True),
        sa.Column("ai", JsonB, nullable=True),
        sa.Column("ai_live", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("artifact_ref", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ats_analysis")

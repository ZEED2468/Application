"""cv_engine: cv_run / cv_run_step state machine

Additive. Creates the two tables backing the CV engine's pipeline state machine
(Slice 0). A `cv_run` is one pass of a CV through the pipeline; `cv_run_step`
records each transition for resumability + audit + cost accounting. No existing
table is altered; nothing to backfill.

Revision ID: cf9a1b2c3d4e
Revises: d5e6f7a8b9c0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "cf9a1b2c3d4e"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "cv_run",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("state", sa.String(length=32), server_default="ingested", nullable=False),
        sa.Column("mode", sa.String(length=32), server_default="fresh_build", nullable=False),
        sa.Column("input", JsonB, nullable=True),
        sa.Column("ledger_snapshot", JsonB, nullable=True),
        sa.Column("registry_version", sa.String(length=64), nullable=True),
        sa.Column("template_id", sa.String(length=64), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("violations", JsonB, nullable=True),
        sa.Column("delta", JsonB, nullable=True),
        sa.Column("artifact_ref", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.create_table(
        "cv_run_step",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("cv_run.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=True),
        sa.Column("violations", JsonB, nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
        sa.Column("detail", JsonB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cv_run_step")
    op.drop_table("cv_run")

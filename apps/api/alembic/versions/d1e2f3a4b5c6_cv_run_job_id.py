"""cv_engine: cv_run.job_id — scope a run to a job

Additive. Adds a nullable `job_id` FK to `cv_run` so a run can be scoped to a job
(the workspace "format fixes" flow); NULL keeps the standalone POST /cv/runs path.
No existing data to backfill.

Revision ID: d1e2f3a4b5c6
Revises: cf9a1b2c3d4e
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "cf9a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cv_run",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id", ondelete="CASCADE"),
                  nullable=True),
    )
    op.create_index("ix_cv_run_job_id", "cv_run", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_cv_run_job_id", table_name="cv_run")
    op.drop_column("cv_run", "job_id")

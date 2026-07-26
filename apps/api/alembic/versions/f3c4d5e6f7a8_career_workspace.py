"""Career Workspace profile fields (R8)

Additive-only. MasterProfile gains preferred locations / job types / salary.

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3c4d5e6f7a8"
down_revision: str | None = "f2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("master_profile", sa.Column("preferred_locations", JsonB, nullable=True))
    op.add_column("master_profile", sa.Column("preferred_job_types", JsonB, nullable=True))
    op.add_column("master_profile", sa.Column("salary_expectation", JsonB, nullable=True))


def downgrade() -> None:
    op.drop_column("master_profile", "salary_expectation")
    op.drop_column("master_profile", "preferred_job_types")
    op.drop_column("master_profile", "preferred_locations")

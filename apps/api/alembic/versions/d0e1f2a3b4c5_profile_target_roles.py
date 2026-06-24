"""master_profile.target_roles: explicit job titles to scrape for

Additive-only. JSON list of role titles the hunter targets; discovery filters scraped
jobs to these.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e1f2a3b4c5"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("master_profile", sa.Column("target_roles", JsonB, nullable=True))


def downgrade() -> None:
    op.drop_column("master_profile", "target_roles")

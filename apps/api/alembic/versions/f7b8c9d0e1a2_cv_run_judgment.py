"""cv_engine: cv_run.judgment — advisory LLM judgment read (Slice 6)

Additive. Adds a nullable JsonB `judgment` column to `cv_run` holding the LLM judgment
layer's output — semantic JD-coverage rescue + an advisory fit verdict. NULL on every run
made offline or without a JD, and never feeds the score or release decision (judgment is
second, on the deterministic floor). No existing data to backfill.

Revision ID: f7b8c9d0e1a2
Revises: e2f3a4b5c6d7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f7b8c9d0e1a2"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("cv_run", sa.Column("judgment", JsonB, nullable=True))


def downgrade() -> None:
    op.drop_column("cv_run", "judgment")

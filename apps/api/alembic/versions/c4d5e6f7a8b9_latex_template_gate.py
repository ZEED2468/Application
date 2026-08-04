"""latex_template.gate: cached ATS format gate from a trial compile

Additive. Adds a nullable JSON `gate` column to `latex_template` so the format-gate
result (computed by a trial compile when a template is uploaded/saved) is cached
against the template. No data migration.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("latex_template", sa.Column("gate", JsonB, nullable=True))


def downgrade() -> None:
    op.drop_column("latex_template", "gate")

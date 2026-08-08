"""cv_engine: cv_run output columns (Slice 9)

Additive. The engine now exposes what it actually produced so generation can persist it as the
GeneratedCv: result_cv_json (the final patched cv_json), breakdown (the ats.score dict), and tex
(the LaTeX source). All nullable; NULL for a run that suspended before render.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b9c0d1e2f3a4"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("cv_run", sa.Column("result_cv_json", JsonB, nullable=True))
    op.add_column("cv_run", sa.Column("breakdown", JsonB, nullable=True))
    op.add_column("cv_run", sa.Column("tex", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cv_run", "tex")
    op.drop_column("cv_run", "breakdown")
    op.drop_column("cv_run", "result_cv_json")

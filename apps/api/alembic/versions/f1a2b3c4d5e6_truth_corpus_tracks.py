"""expanded truth corpus + track-centric fields

Additive-only. MasterProfile gains structured verified extras + per-track career
preferences; User gains an active_track selector.

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("master_profile", sa.Column("verified_extras", JsonB, nullable=True))
    op.add_column("master_profile", sa.Column("preferred_skills", JsonB, nullable=True))
    op.add_column("master_profile", sa.Column("career_preferences", JsonB, nullable=True))
    op.add_column("user", sa.Column("active_track", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "active_track")
    op.drop_column("master_profile", "career_preferences")
    op.drop_column("master_profile", "preferred_skills")
    op.drop_column("master_profile", "verified_extras")

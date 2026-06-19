"""manual chat: editable company on chat_session

Additive-only. Adds a nullable `company` column to `chat_session` so the VA can
correct the auto-extracted company before generating.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_session", sa.Column("company", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_session", "company")

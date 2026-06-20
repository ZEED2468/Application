"""Store login PIN hash on VA accounts."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "va",
        sa.Column("pin_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("va", "pin_hash")

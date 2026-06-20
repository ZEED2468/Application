"""Expand tracker_status values: not_applied, offer, rejection."""

from __future__ import annotations

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("UPDATE application SET tracker_status = 'offer' WHERE tracker_status = 'accepted'")
    op.execute("UPDATE application SET tracker_status = 'rejection' WHERE tracker_status = 'rejected'")


def downgrade() -> None:
    op.execute("UPDATE application SET tracker_status = 'accepted' WHERE tracker_status = 'offer'")
    op.execute("UPDATE application SET tracker_status = 'rejected' WHERE tracker_status = 'rejection'")

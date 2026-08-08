"""cv_engine: TRUE_GAP suspension wiring (Slice 7)

Additive. Three nullable columns for the gap-suspension bridge:
- cv_run.needs_input (JsonB) — {session_id, slots} while the run is suspended at NEEDS_INPUT.
- chat_session.cv_run_id (FK -> cv_run.id) — links a session holding a run's TRUE_GAP prompts
  back to that run so answering them resumes it.
- chat_prompt.slot (String) — which CV slot a missing_section gap prompt fills.
No existing data to backfill; the manual-chat path leaves all three NULL.

Revision ID: a8b9c0d1e2f3
Revises: f7b8c9d0e1a2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "f7b8c9d0e1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("cv_run", sa.Column("needs_input", JsonB, nullable=True))
    op.add_column(
        "chat_session",
        sa.Column("cv_run_id", sa.Uuid(), sa.ForeignKey("cv_run.id", ondelete="CASCADE"),
                  nullable=True),
    )
    op.create_index("ix_chat_session_cv_run_id", "chat_session", ["cv_run_id"])
    op.add_column("chat_prompt", sa.Column("slot", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_prompt", "slot")
    op.drop_index("ix_chat_session_cv_run_id", table_name="chat_session")
    op.drop_column("chat_session", "cv_run_id")
    op.drop_column("cv_run", "needs_input")

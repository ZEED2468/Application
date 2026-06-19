"""invite: email-scoped one-time signup keys

Additive-only. Adds the `invite` table used by the admin->hunter and hunter->VA
signup flows. The frozen entities are untouched.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("va_name", sa.String(length=200), nullable=True),
        sa.Column("va_whatsapp_jid", sa.String(length=128), nullable=True),
        sa.Column("track", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_invite_key_hash"),
    )
    op.create_index("ix_invite_email", "invite", ["email"])
    op.create_index("ix_invite_invited_by_user_id", "invite", ["invited_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_invite_invited_by_user_id", table_name="invite")
    op.drop_index("ix_invite_email", table_name="invite")
    op.drop_table("invite")

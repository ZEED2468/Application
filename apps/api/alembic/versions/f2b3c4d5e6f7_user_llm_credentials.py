"""user_llm_credential: per-user encrypted LLM provider keys (R1)

Additive-only. New table holding each hunter's own (encrypted) provider API key.

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_llm_credential",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_llm_credential_user_provider"),
    )


def downgrade() -> None:
    op.drop_table("user_llm_credential")

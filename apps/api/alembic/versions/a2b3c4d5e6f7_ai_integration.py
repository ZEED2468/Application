"""ai_integration: multi-integration AI provider config (evolve BYO-key)

Additive. Creates the `ai_integration` table (the generalized, multi-per-user
successor to `user_llm_credential`) and backfills existing per-provider keys into it
so no one loses their configured provider. The old table is retained for rollback.

Revision ID: a2b3c4d5e6f7
Revises: f5a6b7c8d9e0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ai_integration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("template", sa.String(length=32), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("config", JsonB, nullable=True),
        sa.Column("models", JsonB, nullable=True),
        sa.Column("capabilities", JsonB, nullable=True),
        sa.Column("status", sa.String(length=24), server_default="unknown", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Backfill from the earlier per-provider table so existing keys carry over.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO ai_integration
              (id, user_id, name, provider, template, base_url, encrypted_api_key, model,
               config, models, capabilities, status, is_default, created_at, updated_at)
            SELECT gen_random_uuid(), user_id, initcap(provider), provider, provider,
                   base_url, encrypted_api_key, model,
                   '{}'::jsonb, '[]'::jsonb, '{}'::jsonb,
                   COALESCE(status, 'unknown'), COALESCE(is_preferred, false), now(), now()
            FROM user_llm_credential
            WHERE encrypted_api_key IS NOT NULL
            """
        )


def downgrade() -> None:
    op.drop_table("ai_integration")

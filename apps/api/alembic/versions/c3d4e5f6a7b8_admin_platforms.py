"""admin platforms: platform table + user/invite.platform_id

Additive-only. Adds the `platform` table and a nullable `platform_id` on `user`
and `invite`. FKs are SQLite-guarded (SQLite can't ALTER-ADD a constraint), same
as the manual-path migration.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_platform_slug"),
    )

    op.add_column("user", sa.Column("platform_id", sa.Uuid(), nullable=True))
    op.create_index("ix_user_platform_id", "user", ["platform_id"])
    op.add_column("invite", sa.Column("platform_id", sa.Uuid(), nullable=True))

    # SQLite can't ALTER-ADD a constraint; the FK is only enforced on Postgres.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_user_platform", "user", "platform", ["platform_id"], ["id"], ondelete="SET NULL"
        )
        op.create_foreign_key(
            "fk_invite_platform", "invite", "platform", ["platform_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_invite_platform", "invite", type_="foreignkey")
        op.drop_constraint("fk_user_platform", "user", type_="foreignkey")
    op.drop_column("invite", "platform_id")
    op.drop_index("ix_user_platform_id", table_name="user")
    op.drop_column("user", "platform_id")
    op.drop_table("platform")

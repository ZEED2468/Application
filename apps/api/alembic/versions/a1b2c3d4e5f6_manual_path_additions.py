"""manual path: role_cv, cover_letter(+template), chat, ats, tracker, audit

Additive-only migration. Adds 6 new tables and new nullable/defaulted columns to
job / generated_cv / application. The frozen 13 entities are never altered.

Revision ID: a1b2c3d4e5f6
Revises: f02bb8c1792d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f02bb8c1792d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JsonB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    # --- role_cv ---
    op.create_table(
        "role_cv",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("track", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("source_file_key", sa.String(length=512), nullable=True),
        sa.Column("parse_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "track", name="uq_role_cv_user_track"),
    )
    op.create_index("ix_role_cv_user_id", "role_cv", ["user_id"])

    # --- cover_letter_template ---
    op.create_table(
        "cover_letter_template",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_cl_template_user"),
    )
    op.create_index("ix_cover_letter_template_user_id", "cover_letter_template", ["user_id"])

    # --- cover_letter ---
    op.create_table(
        "cover_letter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("tex_key", sa.String(length=512), nullable=True),
        sa.Column("pdf_key", sa.String(length=512), nullable=True),
        sa.Column("pdf_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="rendering"),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_id"], ["cover_letter_template.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_cover_letter_job"),
    )
    op.create_index("ix_cover_letter_user_id", "cover_letter", ["user_id"])
    op.create_index("ix_cover_letter_job_id", "cover_letter", ["job_id"])

    # --- chat_session ---
    op.create_table(
        "chat_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("va_id", sa.Uuid(), nullable=True),
        sa.Column("surface", sa.String(length=16), nullable=False, server_default="dashboard"),
        sa.Column("state", sa.String(length=24), nullable=False, server_default="started"),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("jd_url", sa.Text(), nullable=True),
        sa.Column("role_title", sa.String(length=255), nullable=True),
        sa.Column("track", sa.String(length=32), nullable=True),
        sa.Column("role_cv_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("ats_score", sa.Float(), nullable=True),
        sa.Column("ats_breakdown", JsonB, nullable=True),
        sa.Column("confirmed_facts", JsonB, nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["va_id"], ["va.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_cv_id"], ["role_cv.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_session_user_id", "chat_session", ["user_id"])

    # --- chat_prompt ---
    op.create_table(
        "chat_prompt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("chat_session_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("options", JsonB, nullable=True),
        sa.Column("selected", JsonB, nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_prompt_user_id", "chat_prompt", ["user_id"])
    op.create_index("ix_chat_prompt_chat_session_id", "chat_prompt", ["chat_session_id"])

    # --- application_event (audit trail) ---
    op.create_table(
        "application_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=48), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("detail", JsonB, nullable=True),
        *_ts(),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["application_id"], ["application.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_event_user_id", "application_event", ["user_id"])
    op.create_index("ix_application_event_application_id", "application_event", ["application_id"])
    op.create_index("ix_app_event_app_created", "application_event", ["application_id", "created_at"])

    # --- additive columns on the frozen tables ---
    op.add_column("job", sa.Column("origin", sa.String(length=16), nullable=False, server_default="auto"))
    op.add_column("job", sa.Column("role_title", sa.String(length=255), nullable=True))

    op.add_column("generated_cv", sa.Column("source_role_cv_id", sa.Uuid(), nullable=True))
    op.add_column("generated_cv", sa.Column("ats_score", sa.Float(), nullable=True))
    op.add_column("generated_cv", sa.Column("ats_breakdown", JsonB, nullable=True))
    # SQLite can't ALTER-ADD a constraint; the FK is only enforced on Postgres
    # (production). The column exists regardless.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_generated_cv_role_cv", "generated_cv", "role_cv",
            ["source_role_cv_id"], ["id"], ondelete="SET NULL",
        )

    op.add_column(
        "application",
        sa.Column("tracker_status", sa.String(length=16), nullable=False, server_default="applied"),
    )


def downgrade() -> None:
    op.drop_column("application", "tracker_status")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_generated_cv_role_cv", "generated_cv", type_="foreignkey")
    op.drop_column("generated_cv", "ats_breakdown")
    op.drop_column("generated_cv", "ats_score")
    op.drop_column("generated_cv", "source_role_cv_id")
    op.drop_column("job", "role_title")
    op.drop_column("job", "origin")
    op.drop_table("application_event")
    op.drop_table("chat_prompt")
    op.drop_table("chat_session")
    op.drop_table("cover_letter")
    op.drop_table("cover_letter_template")
    op.drop_table("role_cv")

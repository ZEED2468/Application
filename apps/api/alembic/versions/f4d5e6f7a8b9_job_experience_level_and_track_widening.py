"""job.experience_level + widen track columns (capture out-of-band DDL)

Some `job` schema changes were applied to production via ad-hoc scripts
(scripts/add_col.py, alter_db.py, drop_constraints.py) rather than migrations, so a
fresh `alembic upgrade head` was missing them. This migration captures them
idempotently so both a clean DB and the already-patched production DB converge:

- add `experience_level VARCHAR(50)` (matches Job.experience_level)
- widen `track` / `track_override` to VARCHAR(50) (allow custom track strings)
- drop any CHECK constraints on `job` that reference track/track_override

Postgres-only: the test suite builds the schema from the models via create_all, so
this no-ops on any non-postgres dialect.

Revision ID: f4d5e6f7a8b9
Revises: f3c4d5e6f7a8
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4d5e6f7a8b9"
down_revision: str | None = "f3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Additive + idempotent so it's safe whether or not the ad-hoc scripts already ran.
    op.execute("ALTER TABLE job ADD COLUMN IF NOT EXISTS experience_level VARCHAR(50)")
    op.execute("ALTER TABLE job ALTER COLUMN track TYPE VARCHAR(50)")
    op.execute("ALTER TABLE job ALTER COLUMN track_override TYPE VARCHAR(50)")
    op.execute(
        """
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN
                SELECT tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.check_constraints cc
                  ON tc.constraint_name = cc.constraint_name
                WHERE tc.table_name = 'job'
                  AND cc.check_clause ILIKE '%track%'
            LOOP
                EXECUTE format('ALTER TABLE job DROP CONSTRAINT %I', r.constraint_name);
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # Only the additive column is reverted; the track type-widening is left in place
    # (narrowing could truncate custom-track data), and dropped CHECK constraints are
    # not recreated.
    op.execute("ALTER TABLE job DROP COLUMN IF EXISTS experience_level")

#!/usr/bin/env bash
# Container entrypoint for the API image (also used by worker/beat).
#
# Optionally applies DB migrations, then execs the passed command (the compose
# `command:` for each service). Set RUN_MIGRATIONS=0 to skip migrations — useful
# so only the `api` service migrates and worker/beat just start.
set -euo pipefail

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] running: alembic upgrade head"
  if ! alembic upgrade head; then
    echo "[entrypoint] alembic upgrade failed" >&2
    if [ -z "${DATABASE_URL:-}" ]; then
      echo "[entrypoint] hint: DATABASE_URL is not set — link a Render Postgres DB to this service" >&2
    elif echo "${DATABASE_URL}" | grep -qE '@(postgres|redis|bridge)(:|/)'; then
      echo "[entrypoint] hint: DATABASE_URL uses a Docker Compose hostname — use Render's Internal Database URL instead" >&2
    fi
    exit 1
  fi
fi

exec "$@"

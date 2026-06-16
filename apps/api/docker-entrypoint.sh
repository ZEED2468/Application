#!/usr/bin/env bash
# Container entrypoint for the API image (also used by worker/beat).
#
# Optionally applies DB migrations, then execs the passed command (the compose
# `command:` for each service). Set RUN_MIGRATIONS=0 to skip migrations — useful
# so only the `api` service migrates and worker/beat just start.
set -euo pipefail

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] running: alembic upgrade head"
  alembic upgrade head || {
    echo "[entrypoint] alembic upgrade failed" >&2
    exit 1
  }
fi

exec "$@"

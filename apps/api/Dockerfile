# syntax=docker/dockerfile:1
#
# JD Engine API image (FastAPI + Celery, Python 3.12).
# Also used unchanged for the `worker` and `beat` services in compose.
#
# Runtime needs the `tectonic` LaTeX engine on PATH for CV PDF rendering
# (Pipeline A). We pull the official static linux x86_64 release so we don't
# drag in a full TeX Live install.

FROM python:3.12-slim

# uv (fast installer) from the official distroless image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System deps:
#  - curl / ca-certificates: fetch the tectonic release
#  - libfontconfig1 + fonts: tectonic needs fontconfig + at least one font family
#    at render time for the CV templates.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libfontconfig1 \
        fontconfig \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install tectonic: official static musl release, pinned for reproducibility.
# Lands at /usr/local/bin/tectonic (already on PATH).
ARG TECTONIC_VERSION=0.15.0
RUN set -eux; \
    url="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz"; \
    curl -fsSL "$url" -o /tmp/tectonic.tar.gz; \
    tar -xzf /tmp/tectonic.tar.gz -C /usr/local/bin tectonic; \
    rm /tmp/tectonic.tar.gz; \
    tectonic --version

WORKDIR /app

# Copy the project (source + pyproject) then install it + its deps. Editable
# install needs the `app` package present, so source must be copied first.
COPY . .
RUN uv pip install --system -e .

EXPOSE 8000

# Run migrations on container start, then exec the service command (uvicorn /
# celery / beat). `alembic upgrade head` is idempotent and safe to run from
# every replica at boot. To skip (e.g. for the worker/beat), the compose command
# overrides this CMD; entrypoint still runs migrations once per container — set
# RUN_MIGRATIONS=0 to disable.
ENV RUN_MIGRATIONS=1
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# JD Engine — developer entrypoints.
#
# ONE central env file drives every container. Default is ./.env (repo root).
# Point at another file with ENV=... (absolute path), e.g.:
#   make up   ENV=/opt/jd/prod.env
#   make dev  ENV=$(pwd)/.env.staging
ENV ?= $(CURDIR)/.env
export ENV_FILE := $(ENV)

# `--env-file` feeds compose interpolation; the exported ENV_FILE feeds the
# `env_file:` injection — same file for both.
COMPOSE      := docker compose --env-file "$(ENV)" -f infra/docker-compose.yml
COMPOSE_FULL := $(COMPOSE) -f infra/docker-compose.nginx.yml

.PHONY: dev up down logs migrate seed openapi test fmt envcheck

## dev: build + start the app stack (no nginx) — local development
dev:
	$(COMPOSE) up --build

## up: build + start the FULL stack incl. nginx (-d) — server / production
up:
	$(COMPOSE_FULL) up -d --build

## down: stop the stack and remove containers/network (volumes are kept)
down:
	$(COMPOSE_FULL) down

## logs: tail logs from all services
logs:
	$(COMPOSE_FULL) logs -f --tail=200

## migrate: apply DB migrations inside the running api container
migrate:
	$(COMPOSE) exec api alembic upgrade head

## seed: bootstrap dev data (3 hunters, 1 VA, profiles, role CVs, 9 domains)
seed:
	$(COMPOSE) exec api python -m scripts.seed

## envcheck: show which env file is in use + the resolved config
envcheck:
	@echo "Using env file: $(ENV)"
	@$(COMPOSE) config >/dev/null && echo "compose config: OK"

## openapi: export the Swagger/OpenAPI spec + static docs to docs/api/
openapi:
	cd apps/api && uv run python -m scripts.export_openapi

## test: run the api test suite (pytest)
test:
	cd apps/api && uv run pytest

## fmt: format + lint-fix the api code with ruff
fmt:
	cd apps/api && uv run ruff format . && uv run ruff check --fix .

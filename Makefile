# JD Engine — developer entrypoints.
# Most targets wrap the compose stack in infra/docker-compose.yml.

COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: dev down logs migrate seed openapi test fmt

## dev: build images and start the full stack (postgres, redis, api, worker, beat, wa-bridge, web)
dev:
	$(COMPOSE) up --build

## down: stop the stack and remove containers/network (volumes are kept)
down:
	$(COMPOSE) down

## logs: tail logs from all services
logs:
	$(COMPOSE) logs -f --tail=200

## migrate: apply DB migrations inside the running api container
migrate:
	$(COMPOSE) exec api alembic upgrade head

## seed: bootstrap dev data (3 hunters, 1 VA, profiles, role CVs, 9 domains)
seed:
	$(COMPOSE) exec api python -m scripts.seed

## openapi: export the Swagger/OpenAPI spec + static docs to docs/api/
openapi:
	cd apps/api && uv run python -m scripts.export_openapi

## test: run the api test suite (pytest)
test:
	cd apps/api && uv run pytest

## fmt: format + lint-fix the api code with ruff
fmt:
	cd apps/api && uv run ruff format . && uv run ruff check --fix .

COMPOSE       := docker compose
COMPOSE_PROD  := docker compose -f docker-compose.yml -f compose.prod.yml
API_EXEC      := $(COMPOSE) exec -T api

.DEFAULT_GOAL := help
.PHONY: help dev up down logs ps seed status verify-chain migrate revision shell-api \
        shell-db test lint fmt typecheck build-prod up-prod clean reset

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ── local development ───────────────────────────────────────────────────────────

dev: ## Start the stack and seed it (first-run command)
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	$(COMPOSE) up -d --build
	@echo "Waiting for the API to become ready…"
	@until curl -fsS http://localhost:8000/readyz >/dev/null 2>&1; do sleep 1; done
	@$(MAKE) --no-print-directory seed
	@echo ""
	@echo "  Demarc is up."
	@echo "    app       http://localhost:5173"
	@echo "    api docs  http://localhost:8000/api/docs"
	@echo "    mail      http://localhost:8025"
	@echo "    minio     http://localhost:9001"
	@echo ""

up: ## Start the stack without seeding
	$(COMPOSE) up -d --build

down: ## Stop the stack, keep data
	$(COMPOSE) down

logs: ## Tail logs (make logs S=api)
	$(COMPOSE) logs -f $(S)

ps: ## Show service status
	$(COMPOSE) ps

# ── database & data ─────────────────────────────────────────────────────────────

migrate: ## Apply migrations
	$(COMPOSE) run --rm migrate

revision: ## Autogenerate a migration (make revision M="add artifacts")
	@test -n "$(M)" || (echo "Usage: make revision M=\"message\"" && exit 1)
	$(COMPOSE) run --rm \
		-e DEMARC_MIGRATION_DATABASE_URL=postgresql+asyncpg://demarc:demarc@postgres:5432/demarc \
		migrate alembic revision --autogenerate -m "$(M)"

seed: ## Create the local demo organization
	@$(API_EXEC) python -m demarc.cli seed

status: ## Show deployment status
	@$(API_EXEC) python -m demarc.cli status

verify-chain: ## Re-derive and verify every organization's audit chain
	@$(API_EXEC) python -m demarc.cli verify-chain

shell-api: ## Shell into the api container
	$(COMPOSE) exec api /bin/bash

shell-db: ## psql as the least-privileged runtime role (RLS applies)
	$(COMPOSE) exec postgres psql -U demarc_app -d demarc

# ── quality ─────────────────────────────────────────────────────────────────────

test: ## Run the backend test suite
	$(COMPOSE) run --rm --no-deps \
		-e PYTHONPATH=/app/src api \
		sh -c "pip install --quiet pytest pytest-asyncio && python -m pytest tests -q"

lint: ## Lint backend and frontend
	$(COMPOSE) run --rm --no-deps api sh -c "pip install --quiet ruff && ruff check src tests"
	$(COMPOSE) run --rm --no-deps web npm run lint

fmt: ## Format the backend
	$(COMPOSE) run --rm --no-deps api sh -c "pip install --quiet ruff && ruff format src tests && ruff check --fix src tests"

typecheck: ## Typecheck the frontend
	$(COMPOSE) run --rm --no-deps web npm run typecheck

# ── production ──────────────────────────────────────────────────────────────────

build-prod: ## Build the production images
	$(COMPOSE_PROD) build

up-prod: ## Start the production stack
	@test -f .env.production || (echo "Missing .env.production — copy .env.example and fill it in" && exit 1)
	$(COMPOSE_PROD) --env-file .env.production up -d

# ── housekeeping ────────────────────────────────────────────────────────────────

clean: ## Stop the stack and remove volumes (DESTROYS LOCAL DATA)
	$(COMPOSE) down -v

reset: clean dev ## Wipe everything and start fresh

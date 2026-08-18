COMPOSE       := docker compose
COMPOSE_PROD  := docker compose -f docker-compose.yml -f compose.prod.yml
COMPOSE_CI    := docker compose -f docker-compose.yml -f compose.ci.yml
API_EXEC      := $(COMPOSE) exec -T api

# Quality tooling runs natively against the deployment's Python version, not the host's.
PY            := python3.12
VENV          := apps/api/.venv
VENV_BIN      := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help dev up down logs ps seed status verify-chain migrate revision shell-api \
        shell-db venv test test-integration smoke lint fmt typecheck lock \
        build-prod up-prod clean reset

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-17s\033[0m %s\n", $$1, $$2}'

# ── local development ───────────────────────────────────────────────────────────

dev: ## Start the stack and seed it (first-run command)
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	$(COMPOSE) up -d --build
	@echo "Waiting for the API to become ready…"
	@i=0; until curl -fsS http://localhost:8000/readyz >/dev/null 2>&1; do \
		i=$$((i+1)); \
		if [ $$i -ge 120 ]; then \
			echo "The API did not become ready within 120s. Recent logs:"; \
			$(COMPOSE) logs --no-color --tail=40 api migrate; \
			exit 1; \
		fi; \
		sleep 1; \
	done
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

# Quality runs natively, in a venv, not through compose. The old compose-based targets
# could not work: Dockerfile.api never copies `tests/`, the container runs as a non-root
# user so an in-container `pip install` is denied, and the `web` service exists only in
# the local override. Running the same commands CI runs also means a green `make lint`
# means something.
$(VENV): apps/api/pyproject.toml apps/api/requirements-dev.txt
	$(PY) -m venv $(VENV)
	$(VENV_BIN)/pip install --quiet --upgrade pip
	$(VENV_BIN)/pip install --quiet --require-hashes -r apps/api/requirements-dev.txt
	@touch $(VENV)

venv: $(VENV) ## Create the backend virtualenv

test: $(VENV) ## Run the offline backend test suite
	cd apps/api && PYTHONPATH=src $(CURDIR)/$(VENV_BIN)/python -m pytest -q -m "not integration"

test-integration: $(VENV) ## Run the tenant-isolation suite (needs a running stack)
	cd apps/api && PYTHONPATH=src \
		DEMARC_MIGRATION_DATABASE_URL=postgresql+asyncpg://$(or $(POSTGRES_USER),demarc):$(or $(POSTGRES_PASSWORD),demarc)@localhost:5432/$(or $(POSTGRES_DB),demarc) \
		DEMARC_DATABASE_URL=postgresql+asyncpg://demarc_app:$(or $(DEMARC_APP_DB_PASSWORD),demarc_app)@localhost:5432/$(or $(POSTGRES_DB),demarc) \
		$(CURDIR)/$(VENV_BIN)/python -m pytest -q -m integration

smoke: ## Run the end-to-end assertions against the running stack
	bash scripts/smoke.sh

lint: $(VENV) ## Lint backend and frontend
	cd apps/api && $(CURDIR)/$(VENV_BIN)/ruff check src tests alembic
	cd apps/api && $(CURDIR)/$(VENV_BIN)/ruff format --check src tests
	cd apps/web && npm run lint

fmt: $(VENV) ## Format the backend
	cd apps/api && $(CURDIR)/$(VENV_BIN)/ruff format src tests
	cd apps/api && $(CURDIR)/$(VENV_BIN)/ruff check --fix src tests alembic

typecheck: $(VENV) ## Typecheck the backend (mypy strict) and the frontend
	cd apps/api && $(CURDIR)/$(VENV_BIN)/mypy src
	cd apps/web && npm run typecheck

lock: $(VENV) ## Regenerate the dependency locks after editing pyproject.toml
	cd apps/api && $(CURDIR)/$(VENV_BIN)/uv pip compile pyproject.toml \
		--generate-hashes --python-version 3.12 -o requirements.txt
	cd apps/api && $(CURDIR)/$(VENV_BIN)/uv pip compile pyproject.toml --extra dev \
		--generate-hashes --python-version 3.12 -o requirements-dev.txt

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

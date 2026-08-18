# Demarc

[![ci](https://github.com/troyteodoro/PCI-Tools-Suite/actions/workflows/ci.yml/badge.svg)](https://github.com/troyteodoro/PCI-Tools-Suite/actions/workflows/ci.yml)
[![stack](https://github.com/troyteodoro/PCI-Tools-Suite/actions/workflows/stack.yml/badge.svg)](https://github.com/troyteodoro/PCI-Tools-Suite/actions/workflows/stack.yml)

PCI DSS v4.0.1 evidence and scope tooling for the security engineer running an annual
validation — or a company reaching its first compliance.

Five tools over one evidence spine: **Payment Page Monitor**, **Scope Map**, **Scope Drift
Detector**, **PCI Checklist**, **ROC Export**.

> Demarc reports what evidence exists, what is missing, and what a rule found. It never
> states that a control is compliant — that determination belongs to your assessor.

See [PLAN.md](PLAN.md) for the full architecture, data model and milestone plan.

## Quick start

Requires Docker with Compose v2.

```bash
make dev
```

That builds the stack, applies migrations, seeds a local organization, and prints where
everything is:

| | |
|---|---|
| App | http://localhost:5173 |
| API docs | http://localhost:8000/api/docs |
| Mail (Mailpit) | http://localhost:8025 |
| Object storage (MinIO) | http://localhost:9001 |

Sign in with `engineer@northgate.example` / `demarc-local-dev-2026`. These are local
development credentials; seeding refuses to run against a production deployment.

```
make help              # every target
make logs S=api        # tail one service
make test              # offline backend suite
make test-integration  # tenant isolation, against the running stack
make smoke             # end-to-end assertions against the running stack
make lint              # ruff + eslint
make typecheck         # mypy strict + tsc
make lock              # regenerate the dependency locks
make verify-chain      # re-derive and verify the audit chain
make clean             # stop and destroy local data
```

## Status

**M0 complete, with CI.** Application shell, tenant isolation, authentication, RBAC and
the hash-chained audit log, behind gates that block a merge. The five tools are
placeholders that name the milestone they arrive in — see PLAN.md §11.

## Continuous integration

Every pull request runs `ci.yml`: `api` (ruff, mypy strict, offline pytest on Python
3.12), `web` (eslint, tsc, vite build), and `db` — which applies the migrations to a real
Postgres, checks there is exactly one head, runs `alembic check`, round-trips
downgrade/upgrade, and executes the tenant-isolation suite. Backend and infra changes also
run `stack.yml`, which builds the three images and runs `scripts/smoke.sh` against the
composed deployment.

Two of those gates will shape how you work:

- **`alembic check`** fails when the models and the migrations disagree, so migrations are
  generated (`make revision M="…"`) rather than hand-edited to approximate the models.
- **The tenant-isolation suite** is parametrized over `DATA_PLANE_TABLES`. Register a new
  data-plane table and it is immediately checked for RLS, `FORCE`, a policy and a grant —
  you do not write a test for it, and you cannot skip one.

Backend dependencies are hash-pinned in `apps/api/requirements.txt` (runtime, what the
images install) and `requirements-dev.txt` (adds the tooling). After editing
`pyproject.toml`, run `make lock` — CI rejects a change to one without the other.

See [ADR 0002](docs/adr/0002-ci-gates.md) for why this came before M1 and what it caught.

## Layout

```
apps/web        React 19 + TypeScript + Vite
apps/api        FastAPI + SQLAlchemy 2.0 + Alembic; also builds the ARQ worker image
  tests/            offline suite — no database, no network
  tests/integration tenant isolation; needs a live Postgres
infra/          Postgres init, Caddy config
scripts/        smoke.sh — end-to-end assertions against a running stack
.github/        workflows, Dependabot, PR template
docs/adr/       decision records
docs/mockups/   the UI design spec (two themes: Modernist, Nocturne)
```

## Things worth knowing before you change anything

**Evidence artifacts are immutable and content-addressed.** Never update or delete —
supersede. `collected_at` (when the evidence was true) is distinct from `ingested_at`.

**Tenant isolation has two planes.** Data-plane tables carry `org_id` and are protected by
forced Postgres RLS; the application connects as a non-owner role with no `BYPASSRLS`. All
data-plane queries must go through `org_session()`. Read
[docs/adr/0001](docs/adr/0001-tenant-isolation.md) before adding a table.

**The audit log is append-only in the database**, not by convention — the runtime role
holds no `UPDATE` or `DELETE` grant on it.

**Components read only the `--app-*` semantic CSS tokens**, never the raw ramps. The two
themes are not a straight token swap; `apps/web/src/theme/tokens.css` explains why.

**No cardholder data, ever.** PAN detection runs on ingest from M1.

## Production

```bash
cp .env.example .env.production   # fill in, then place secrets under ./secrets/
make build-prod
make up-prod
```

Production differs from local in ways that matter: images come from a registry pinned by
digest, secrets are mounted files rather than environment variables, only Caddy publishes a
port, and containers run read-only with dropped capabilities. The API refuses to start in
production if any development default survives. See `compose.prod.yml`.

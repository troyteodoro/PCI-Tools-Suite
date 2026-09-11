# Demarc — PCI Tools Suite

This project runs on **spec-driven, task-driven development**. Four documents govern all
work, and every prompt is handled through this routing protocol — strictly, in order:

1. **`docs/constitution.md`** — the rules that cannot be broken. Read it first. It is
   binding, never violated, and never edited without an explicit user-approved amendment.
2. **`docs/tasks.md`** — find the current task. Work proceeds task by task, in order. A
   task not in the file is not worked until it is added (which requires a decision entry).
3. **`docs/spec.md` + `docs/decisions.md`** — read the spec sections and decision entries
   the task references before touching code. Do not re-litigate logged decisions.
4. **`docs/decisions.md` (append)** — any decision, assumption, or discovered oversight
   is appended to the log — and reflected in spec.md / tasks.md — *before* work proceeds.
   The log is append-only: supersede entries, never edit them.

TDD is risk-tiered (constitution §2.2): the failing test comes **before** the
implementation on the strict surfaces (rules engine, tenant isolation, evidence
immutability, PAN detection, audit hash chain); everywhere else tests land in the same
commit/PR. A task is done only when its acceptance criteria are met and the gates have
actually been run and passed (constitution §3.2).

## Quick orientation

- React 19 + TypeScript + Vite frontend, Python 3.12 + FastAPI backend, Postgres 16,
  Redis + ARQ workers, S3-compatible object storage.
- Five tools over one evidence spine: Payment Page Monitor, Scope Map, Scope Drift
  Detector, PCI Checklist, ROC Export. The PCI Coach sidebar is a renderer, not a tool.
- `org_id` is on every org-scoped table and enforced by RLS, even in the single-tenant
  build. Never write a query that omits it.
- The UI mockup in `docs/mockups/` is the design spec. Two themes: Modernist (light) and
  Nocturne (dark), both runtime-selectable, tokens in `_ds/*/styles.css`.

Full architecture, data model, and per-tool specifications: `docs/spec.md`.

## Current state

**M0 and M0.5 complete.** App shell, two-plane tenant isolation with forced RLS, session
auth, RBAC, hash-chained audit log, local + production Docker configurations, CI gates.
`make dev` brings up a working, seeded deployment. Backend: 45 tests (35 offline, 10
tenant-isolation integration), ruff clean, mypy strict clean. Frontend: eslint, typecheck
and production build clean.

**Current milestone: M1 — the evidence spine.** The task breakdown lives in
`docs/tasks.md`; start at the first `todo` task.

### CI

Two workflows, both on pull requests. `ci.yml` runs three path-filtered jobs — `api`
(ruff, mypy strict, offline pytest), `web` (eslint, tsc, vite build), and `db`
(`alembic upgrade`/`check`/round-trip plus the tenant-isolation suite against a real
Postgres). `stack.yml` builds the three images and runs `scripts/smoke.sh` against the
composed deployment; it is path-filtered to backend and infra changes and is not a
required check.

Two gates are worth knowing about before you add tables or rules:

- **`alembic check`** fails if the models and the migrations disagree. Regenerate with
  `make revision M="…"` rather than hand-editing a migration to match.
- **`tests/integration/test_tenant_isolation.py`** is parametrized over
  `DATA_PLANE_TABLES`, so a new data-plane table is covered the moment it is registered.
  A missing policy, a missing `FORCE`, or a forgotten `GRANT` fails the build.

Dependencies are pinned with hashes in `apps/api/requirements*.txt`, which is what both
CI and the images install. After editing `pyproject.toml`, run `make lock` — CI fails a
PR that changes one without the other.

Read `docs/decisions.md` D-0005 before adding or relaxing a gate. It records why CI came
before M1 and, more usefully, why an obvious-looking check can measure nothing — confirm
a new gate fails against the broken state before trusting it (constitution §2.3).

Useful commands: `make dev`, `make test`, `make test-integration`, `make smoke`,
`make lint`, `make typecheck`, `make lock`, `make verify-chain`, `make status`,
`make logs S=api`.

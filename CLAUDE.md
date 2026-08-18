# Demarc — PCI Tools Suite

**Read `PLAN.md` first.** It is the source of truth for scope, architecture, data model,
milestones, and the decisions already made. Do not re-litigate locked decisions in §2.

## Quick orientation

- React 19 + TypeScript + Vite frontend, Python 3.12 + FastAPI backend, Postgres 16,
  Redis + ARQ workers, S3-compatible object storage.
- Five tools over one evidence spine: Payment Page Monitor, Scope Map, Scope Drift
  Detector, PCI Checklist, ROC Export. The PCI Coach sidebar is a renderer, not a tool.
- `org_id` is on every org-scoped table and enforced by RLS, even in the single-tenant
  build. Never write a query that omits it.
- The UI mockup in `docs/mockups/` is the design spec. Two themes: Modernist (light) and
  Nocturne (dark), both runtime-selectable, tokens in `_ds/*/styles.css`.

## Rules that are not negotiable

1. **Evidence artifacts are immutable and content-addressed.** Never update or delete —
   supersede. `collected_at` (when the evidence was true) is distinct from `ingested_at`.
2. **No cardholder data.** PAN detection runs on every ingest; matches are rejected, not
   stored.
3. **Rules are pure functions** over an injected `EvidenceGraph` with an injected clock.
   No I/O, no `datetime.now()`. Every rule ships with fixture tests.
4. **The rules-pack version is stamped on every finding, verdict, and generated artifact.**
   Reproducibility is the reason we chose a deterministic engine over an LLM.
5. **The UI never asserts compliance.** It reports what evidence exists, what is missing,
   and what a rule found. The QSA determines compliance.
6. **The crawler container gets no database or storage credentials.** It renders untrusted
   third-party JavaScript and returns results through the queue only.

## Current state

**M0 complete, plus CI.** App shell, two-plane tenant isolation with forced RLS, session
auth, RBAC, hash-chained audit log, local + production Docker configurations. `make dev`
brings up a working, seeded deployment. Backend: 45 tests (35 offline, 10 tenant-isolation
integration), ruff clean, mypy strict clean. Frontend: eslint, typecheck and production
build clean.

**Next: M1 — the evidence spine** (§4, §11): content-addressed artifacts on S3/MinIO, the
requirement catalog seed, checklist CRUD, evidence linking, PAN detection on ingest.

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

Read [ADR 0002](docs/adr/0002-ci-gates.md) before adding or relaxing a gate. It records
why CI came before M1 and, more usefully, why an obvious-looking check can measure
nothing — confirm a new gate fails against the broken state before trusting it.

Useful commands: `make dev`, `make test`, `make test-integration`, `make smoke`,
`make lint`, `make typecheck`, `make lock`, `make verify-chain`, `make status`,
`make logs S=api`.

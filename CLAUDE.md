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

**M0 complete.** App shell, two-plane tenant isolation with forced RLS, session auth,
RBAC, hash-chained audit log, local + production Docker configurations. `make dev` brings
up a working, seeded deployment. Backend: 26 tests passing, ruff clean. Frontend:
typecheck and production build clean.

**Next: M1 — the evidence spine** (§4, §11): content-addressed artifacts on S3/MinIO, the
requirement catalog seed, checklist CRUD, evidence linking, PAN detection on ingest.

Useful commands: `make dev`, `make test`, `make lint`, `make verify-chain`, `make status`,
`make logs S=api`.

# Demarc — Tasks

**The running order of development.** This file is step 2 of the routing protocol in
`docs/constitution.md`: after the constitution, find the current task here, then read the
`docs/spec.md` sections and `docs/decisions.md` entries it references before touching
code. Work proceeds task by task, in order. Changing this file (adding, reordering, or
re-scoping tasks) requires a `docs/decisions.md` entry.

**Task format.** Each task carries:

- **Status**: `todo` · `in progress` · `done`. A task is `done` only when its acceptance
  criteria are met **and** the relevant gates (lint, typecheck, tests) have been run and
  pass (constitution §3.2).
- **TDD tier**: `strict` (the failing test is written before the implementation —
  constitution §2.2) or `standard` (tests land in the same commit/PR).
- **Spec** references and **Depends on**.

**Completed milestones.**

- **M0 — Scaffolding** ✅ App shell in both themes, two-plane tenant isolation with
  forced RLS (D-0004), session auth, RBAC, hash-chained audit log, local + production
  compose. `make dev` gives a logged-in, seeded app.
- **M0.5 — CI** ✅ Two workflows, hash-pinned locks, tenant-isolation integration suite;
  surfaced and fixed five latent defects (D-0005).

---

## Current milestone: M1 — the evidence spine

Everything in the product hangs off the artifact model (spec §4). Start with the model
itself — content addressing, the `collected_at` / `ingested_at` split, and
supersede-not-update — before the catalog seed or any CRUD. It is the one thing that is
genuinely painful to change once evidence exists. Do not skip ahead to tool milestones.

Two standing gates already cover this work: `alembic check` fails if models and
migrations disagree (regenerate with `make revision M="…"`), and the tenant-isolation
suite covers each new data-plane table the moment it is registered in
`DATA_PLANE_TABLES`.

**Milestone exit:** real evidence can be uploaded (with PAN detection), linked to
checklist items, and reflected in real dashboard rollups — with both new CI gates live.

### M1.1 — Artifact model and migration

Status: todo · TDD tier: **strict** (evidence immutability) · Spec: §4, §5 · Depends on: —

The `artifacts` table per spec §4/§5, on the data plane, registered in
`DATA_PLANE_TABLES`. Service-layer guarantees in `services/`: supersede-never-mutate (a
correction is a new artifact with `superseded_by` set on the old one), `collected_at`
distinct from and never defaulted to `ingested_at`.

Write the failing tests first: updating or deleting an artifact fails; superseding sets
`superseded_by` and leaves the original readable; `collected_at` is required and
caller-supplied while `ingested_at` is server-set.

**Acceptance**
- [ ] Immutability fixture tests pass (written before the implementation)
- [ ] Migration generated via `make revision`; `alembic check` green
- [ ] Tenant-isolation suite covers `artifacts` with no new test code
- [ ] `make lint`, `make typecheck`, `make test` pass

### M1.2 — Content-addressed object storage service

Status: todo · TDD tier: standard · Spec: §3, §4 · Depends on: M1.1

Storage client for MinIO/S3 (bucket from the compose configuration) keyed by SHA-256:
the content address is the storage key. Uploading identical content twice yields one
object and two provenance records. No overwrite path exists.

**Acceptance**
- [ ] Offline tests against a fake store; integration test against MinIO
- [ ] Duplicate-content upload produces one object, two artifact rows
- [ ] `make lint`, `make typecheck`, `make test`, `make test-integration` pass

### M1.3 — PAN detection

Status: todo · TDD tier: **strict** (constitution §1.2) · Spec: §8 · Depends on: —

Luhn-validated PAN detector, written before any upload endpoint exists. Pure and
offline-testable. Fixture vectors first: positives across card brands and separator
styles (contiguous, spaced, dashed); near-miss negatives so a 16-digit order number or a
timestamp is not rejected; scanning of plain text and common container formats.

**Acceptance**
- [ ] Fixture suite (positives + near-miss negatives) written first and passing
- [ ] Detector performs no I/O; testable without a running stack
- [ ] `make lint`, `make typecheck`, `make test` pass

### M1.4 — Ingest endpoint: upload → scan → store

Status: todo · TDD tier: **strict** for the rejection path · Spec: §4, §8 · Depends on: M1.1, M1.2, M1.3

Multipart upload endpoint: PAN scan (M1.3) runs before any write (M1.2). Matches are
rejected with a specific message and nothing is persisted — not in the bucket, not in the
database, not in logs. Accepted files become artifacts with provenance
(`source=upload`, `collected_at` supplied by the uploader, `ingested_at` server-set).
Includes the supersede endpoint. All state changes audit-logged.

**Acceptance**
- [ ] Rejection-path test written first: a rejected upload leaves no trace in bucket,
      database, or application logs
- [ ] Happy path: artifact row + object + audit entry, content-addressed
- [ ] Supersede endpoint sets `superseded_by`; original remains readable
- [ ] `make lint`, `make typecheck`, `make test`, `make test-integration` pass

### M1.5 — Requirement catalog seed

Status: todo · TDD tier: standard · Spec: §5, §6.4 · Depends on: —

`packages/catalog/` with the PCI DSS v4.0.1 seed: requirement **identifiers, titles, our
own paraphrased evidence-expected descriptors, and cadences only** — never the standard's
copyrighted text (spec §6.4 licensing note). `requirement_catalog` table
(org-independent, versioned, so v4.1 can load alongside later). Loader wired into the
existing seed command.

**Acceptance**
- [ ] Seed contains no verbatim PCI DSS requirement text
- [ ] `make dev` seeding loads the catalog; re-running is idempotent
- [ ] `make lint`, `make typecheck`, `make test` pass; `alembic check` green

### M1.6 — Assessments and checklist CRUD

Status: todo · TDD tier: standard · Spec: §5, §6.4 · Depends on: M1.5

`assessments` and `checklist_items` tables per spec §5, data-plane registered. Routers
and services following the existing `api/routers/` + `services/` patterns; checklist
state changes audit-logged. Analyzer fields (`analyzer_verdict`,
`analyzer_rules_version`) exist but stay null until M3.

**Acceptance**
- [ ] CRUD endpoints with RBAC (auditor/viewer read-only)
- [ ] Both tables in `DATA_PLANE_TABLES`; isolation suite green; `alembic check` green
- [ ] `make lint`, `make typecheck`, `make test`, `make test-integration` pass

### M1.7 — Evidence linking

Status: todo · TDD tier: standard · Spec: §4, §5 · Depends on: M1.4, M1.6

`evidence_links` many-to-many between checklist items and artifacts, with a note field.
Link/unlink endpoints; listing a checklist item returns its artifacts with
`collected_at` visible — the compliance-relevant date, not the upload date.

**Acceptance**
- [ ] Link/unlink audit-logged; table registered and isolation-covered
- [ ] Item listing shows linked artifacts with `collected_at`
- [ ] Gates pass (`make lint`, `make typecheck`, `make test`, `make test-integration`)

### M1.8 — Dashboard rollups

Status: todo · TDD tier: standard · Spec: §1, §6.4 · Depends on: M1.7

Rollup endpoint (checklist counts by status, evidence freshness) and the dashboard shell
consuming it through the OpenAPI-generated TypeScript client. Copy states what evidence
exists and what is missing — never that anything *is* compliant (constitution §1.5; the
CI copy grep enforces it).

**Acceptance**
- [ ] Dashboard renders real rollups from the seeded demo org in both themes
- [ ] Web gates pass (eslint, tsc, vite build, compliance-copy grep)

### M1.9 — CI gate: PAN detection

Status: todo · TDD tier: gate (prove-it-fails, constitution §2.3) · Spec: §8, §9 · Depends on: M1.4

M1.3's vector suite as a named CI gate, plus a `scripts/smoke.sh` assertion that a
rejected upload leaves no trace in the bucket *or* any container log.

**Acceptance**
- [ ] Gate confirmed to fail against a deliberately broken detector before it is trusted
- [ ] Smoke assertion runs in `stack.yml` and via `make smoke`

### M1.10 — CI gate: OpenAPI → TypeScript drift

Status: todo · TDD tier: gate (prove-it-fails, constitution §2.3) · Spec: §3, §9 · Depends on: M1.8

Regenerate the TypeScript client from the app's OpenAPI schema in CI; a dirty diff fails
the `web` job. Makes spec §3's "types are never hand-maintained across the boundary"
mechanical.

**Acceptance**
- [ ] Gate confirmed to fail against a hand-edited client before it is trusted
- [ ] Regeneration command documented in the Makefile

---

## Backlog: milestones M2–M8

Ordered by dependency; each is independently demoable. A backlog milestone is decomposed
into tasks when it becomes current — which requires a `docs/decisions.md` entry.

### M2 — Payment Page Monitor
Crawl worker, snapshots, script capture including runtime-injected, SRI verification,
diff, script register, alerting, evidence artifact emit (spec §6.1).
**Exit:** the mockup's Script Monitor screen, live, with a real unapproved-script finding.
**CI additions:** Playwright E2E (the `playwright install` cache is shared with the crawl
image, so the cost is paid once); weekly `pip-audit` / `npm audit` / Trivy scan reporting
to the Security tab rather than blocking PRs; type-aware ESLint once there is real async
UI code for `no-floating-promises` to catch. `tests/test_compose_credentials.py` already
asserts the crawler holds no database or storage credentials — it passes vacuously until
this milestone creates the crawl service.

### M3 — Rules engine + Checklist analyzer + Coach
Engine, first rules pack, analyzer verdicts, risk-ordered gap list, context-scoped Coach
sidebar (spec §6.4, §7).
**Exit:** Checklist screen and the Coach panel on every route.
**CI additions:** the determinism gates the deterministic-engine decision (D-0002) exists
to make possible — a repeated pack run is byte-identical; an AST walk over `rules/**`
rejects I/O, `datetime.now()` and `random`; a changed pack without a version bump fails.

### M4 — Scope Map
Assets, zones, data flows, scope declaration versioning and signing, nested-containment
visualization, scope + data-flow export artifact (spec §6.2).

### M5 — Drift Detector
Observation ingest (file import + payment-monitor source), normalizer, reconciler rules,
findings UI with declared/observed contrast and dispositions (spec §6.3). **Depends on
M4** — there is nothing to compare against without a declared scope.

### M6 — ROC Export
Package builder, manifest, open-items CSV, redaction pass, signed download (spec §6.5).

### M7 — Drift connectors
AWS read-only first (inventory, security groups, buckets, flow logs), then Azure/GCP,
then DNS/network discovery behind the attestation gate (spec §6.3, §8). Brings secret
storage and rotation with it.
**CI additions:** gitleaks becomes worth its noise here, with a `.gitleaks.toml`
allowlisting the deliberate development credentials and custom rules for cloud-connector
key shapes; before this milestone GitHub's push protection covers the same ground without
the false positives.

### M8 — Production hardening + SaaS configuration
Backups, OIDC/SAML, invites, quotas, and **release**: a tag-triggered workflow publishing
the three images to GHCR with build-provenance attestation and an SBOM, capturing each
digest (spec §9). Prerequisite, and it is not cosmetic: `compose.prod.yml` currently pins
by *tag* while its header and spec §9 promise digest pinning — those `image:` lines must
become `@${…_DIGEST}` before a release workflow can deliver what the file claims.

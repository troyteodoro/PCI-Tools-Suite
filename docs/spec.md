# Demarc — Specification

**Requirements, scope, and architecture.** This document says what Demarc is and how it is
built. It is read through the routing protocol in `docs/constitution.md`: constitution
first, then the current task in `docs/tasks.md`, then the sections here that the task
references. Changing this document requires an entry in `docs/decisions.md`. Current
status and the order of work live in `docs/tasks.md`, not here.

---

## 1. What this is

A suite of tools for the security engineer who has to survive a PCI DSS v4.0.1 assessment —
either the annual re-validation, or a company reaching its first compliance.

The product does one thing well: **it turns the messy reality of an environment into dated,
hash-verifiable evidence artifacts, and tells you what is still missing.** It is not an
auditor, not a scanner, and not a compliance determination. It produces the inputs an
assessor asks for, and the list of what you still owe them.

Five tools, one evidence spine:

| Tool | What it does | Requirements it serves |
|---|---|---|
| **Payment Page Monitor** | Crawls a checkout page, inventories every script and its integrity attribute, snapshots state, alerts on change, emits a dated evidence artifact | 6.4.3, 11.6.1 |
| **Scope Map** | Visual map of the CDE, connected-to systems, and the business around them, with evidence still outstanding drawn on each zone | 12.5.2 |
| **Scope Drift Detector** | Compares declared scope against the observed environment, returns contradictions as findings | 12.5.2, 11.4.5, 1.4.2 |
| **PCI Checklist** | Analyzes attached evidence and says what is still needed, requirement by requirement | all |
| **ROC Export** | Assembles template, attestation, and every artifact into one dated, manifested archive | assessment delivery |

The **PCI Coach** is a persistent context-aware advisory sidebar present on every screen,
not a sixth tool. It is fed by the same rules engine that produces findings.

The UI mockup lives in `docs/mockups/` (provided as `PCI Tool.dc.html` +
`PCI Tool Nocturne.dc.html`). It defines the information architecture and both visual
themes. Treat it as the design spec.

> The mockup predates the naming decision and still shows **Perimeter** in the sidebar,
> the tab titles, and the URL `app.perimeter.io/readiness`. The product is **Demarc**;
> replace those strings when porting the UI. "Northgate Retail" in the mockup is the
> fictional demo tenant, not the product.

---

## 2. Decisions

Locked decisions and their rationale live in `docs/decisions.md` — see D-0002 (platform
and product decisions) and D-0003 (M0 assumptions). Do not re-litigate them; superseding
one requires a new decision entry approved by the user.

---

## 3. Architecture

```
                       ┌───────────────────────────────┐
  browser ───TLS──────►│  Caddy (prod) / Vite (local)  │
                       └───────────┬───────────────────┘
                                   │
                   ┌───────────────┴────────────────┐
                   │                                │
          ┌────────▼────────┐            ┌──────────▼──────────┐
          │  web            │            │  api                │
          │  React + Vite   │            │  FastAPI + uvicorn  │
          │  static, nginx  │            │  REST + SSE         │
          └─────────────────┘            └──────────┬──────────┘
                                                    │
                        ┌───────────────────────────┼──────────────────┐
                        │                           │                  │
                 ┌──────▼──────┐            ┌───────▼──────┐   ┌───────▼──────┐
                 │ PostgreSQL  │            │    Redis     │   │  Object      │
                 │     16      │            │  queue+cache │   │  storage     │
                 └─────────────┘            └───────┬──────┘   │ MinIO / S3   │
                                                    │          └───────┬──────┘
                        ┌───────────────────────────┴──────┐           │
                        │                                  │           │
              ┌─────────▼──────────┐          ┌────────────▼───────┐   │
              │  worker-crawl      │          │  worker-general    │   │
              │  ARQ + Playwright  │          │  ARQ               │   │
              │  egress-only net   │          │  drift, ROC build, │   │
              │  Chromium          │          │  analysis, imports │   │
              └────────────────────┘          └────────────────────┘───┘
```

**Why two worker classes.** The Playwright image is ~1.5 GB and reaches out to the public
internet to render untrusted third-party JavaScript. It gets its own image, its own
network policy (egress only, no database access — it returns results through the queue),
and its own scaling profile. Everything else runs in the slim worker.

### Component notes

- **API** — FastAPI, Pydantic v2 for all boundaries, SQLAlchemy 2.0 async, Alembic
  migrations. OpenAPI schema generates the frontend's TypeScript client, so types are
  never hand-maintained across the boundary.
- **Queue** — ARQ (async-native, Redis-backed) rather than Celery. Cron support covers
  scheduled re-crawls and nightly drift runs; the async model matches Playwright's async
  API and FastAPI's without a thread-pool bridge.
- **Object storage** — S3-compatible, MinIO locally. Every stored object is
  **content-addressed by SHA-256**. Uploading identical content twice yields one object
  and two provenance records.
- **Frontend** — React Router for the six routes in the mockup, TanStack Query for all
  server state (no Redux; there is very little client state). Styling is plain CSS with
  custom properties ported from `_ds/*/styles.css` — the mockup's design systems are
  already token-driven, and the component classes (`btn`, `tag`, `table`, `input`,
  `field`) port directly. No CSS framework. The Scope Map's nested-containment diagram
  and the dashboard's evidence timeline are hand-built SVG/CSS grid; neither is a chart
  a charting library draws well.

---

## 4. The evidence spine

Everything in this product hangs off one idea, and getting it right first is what makes
the five tools cohere rather than being five separate apps.

**An evidence artifact is immutable, content-addressed, dated, and carries its provenance.**

```
artifact {
  id, org_id
  sha256              ← content address; the storage key
  kind                ← scan_report | config_export | policy_doc | page_snapshot | ...
  collected_at        ← when the evidence was true, not when it was uploaded
  ingested_at
  source              ← upload | payment_monitor | drift_run | scope_export | connector
  produced_by         ← tool + version + rules-pack version, if machine-generated
  metadata            ← jsonb, kind-specific
  superseded_by       ← artifacts are never edited or deleted, only superseded
  redaction_applied   ← bool + what was redacted
}
```

Rules:

1. **Never mutate.** A corrected artifact is a new artifact with `superseded_by` set on
   the old one. Assessors ask what you knew and when; a mutable store cannot answer.
2. **`collected_at` is the compliance-relevant date**, and it is separate from ingest
   time. A pen test report uploaded today may be 14 months old — that distinction is the
   entire finding in the mockup.
3. **Every machine-generated artifact records the version of the code and rules pack that
   produced it.** This is what makes the deterministic Coach defensible.
4. **The audit log is hash-chained.** Each entry carries the hash of its predecessor. This
   tool's own output is evidence, so its own integrity has to be demonstrable.

Artifacts link many-to-many to checklist items. The checklist analyzer, the scope map's
"evidence outstanding" marks, the drift detector's findings, and the ROC package all read
this same graph. Build it in M1 before any tool.

---

## 5. Data model

Core entities, grouped. Every org-scoped table carries `org_id` with a composite index and
a row-level security policy (enforced even in single-tenant, so the SaaS build inherits a
tested isolation boundary rather than a new one).

**Identity & tenancy**
`organizations` (name, merchant_level, saq_type) · `users` · `memberships` (org_id, role)
· `sessions` · `audit_log` (hash-chained)

**Assessment & requirements**
`requirement_catalog` (standard_version, req_id, parent_id, title, evidence_expected,
cadence) — seeded, org-independent, versioned
`assessments` (org_id, standard_version, saq_type, period_start, period_end,
walkthrough_date)
`checklist_items` (org_id, assessment_id, req_id, status, owner_id, due_date,
analyzer_verdict, analyzer_rules_version)

**Evidence**
`artifacts` (as above) · `evidence_links` (checklist_item_id, artifact_id, note)

**Scope**
`assets` (org_id, name, kind, zone `cde|connected_to|out_of_scope`, identifiers jsonb,
declared bool, first_seen, retired_at)
`data_flows` (org_id, name, hops jsonb, evidenced bool)
`scope_declarations` (org_id, version, confirmed_at, confirmed_by, signed_artifact_id,
frozen snapshot of assets + flows) — immutable versions; 12.5.2 wants a dated,
business-signed confirmation, and re-confirmation after significant change

**Payment page monitoring**
`monitored_pages` (org_id, url, crawl_cron, navigation_steps jsonb, secret_ref)
`page_snapshots` (page_id, captured_at, dom_sha256, response_headers jsonb, csp jsonb,
artifact_id)
`page_scripts` (snapshot_id, src, host, first_party bool, load_type `external|inline|
injected`, integrity_attr, integrity_algo, content_sha256, injected_by)
`script_register` (org_id, page_id, src_pattern, state `authorized|justified|review_due|
unapproved`, business_justification, integrity_method, authorized_by, authorized_at) —
**this is the 6.4.3 inventory**, maintained by humans, compared against observation
`page_changes` (page_id, from_snapshot, to_snapshot, change_type, detail jsonb,
alerted_at) — **this is the 11.6.1 alert history**

**Drift**
`observations` (org_id, source_type, source_run_id, observed_at, raw jsonb,
resolved_asset_id)
`drift_runs` (org_id, scope_declaration_version, sources jsonb, started_at, finished_at,
rules_version)
`findings` (org_id, run_id, rule_id, rules_version, severity, title, declared jsonb,
observed jsonb, requirement_refs[], status `open|accepted|remediated|risk_accepted`,
disposition_note, disposed_by)

**Export**
`roc_packages` (org_id, assessment_id, built_at, archive_artifact_id, manifest_sha256,
open_items_count, options jsonb)

---

## 6. Tool specifications

### 6.1 Payment Page Monitor — *build first*

The highest-value standalone tool and the one with the clearest requirement mapping.

**Crawl.** Playwright/Chromium loads the target. Because payment pages usually sit behind
a flow, each monitored page carries an optional ordered `navigation_steps` script
(add-to-cart → checkout → …). Credentials referenced by secret handle, never stored inline.

**Capture, per snapshot:**
- every `<script>`: external src, inline content, and scripts injected at runtime by other
  scripts (this is the tag-manager case, and it is the one that matters)
- `integrity` attribute presence, algorithm, and whether the value actually matches the
  fetched content
- `crossorigin`, `nonce`, load position, and the initiator chain for injected scripts
- all response headers and the effective CSP
- iframe origins (a hosted payment iframe changes the 6.4.3 analysis materially)
- SHA-256 of every script body actually executed

**Detect.** Diff against the previous snapshot → `page_changes` → alert. Separately,
reconcile the observed script set against `script_register` → unapproved scripts → open
finding. 11.6.1 requires alerting on changes to both headers *and* script content, and a
check at least weekly; default cron is every 30 minutes per the mockup, floor enforced at
weekly.

**Emit.** A dated evidence artifact: JSON containing every script with host, integrity
method, justification from the register, content hash, first-seen date, and the full change
log for the evidence period — plus a rendered PDF for the assessor. Content-addressed,
manifested, attachable to checklist items 6.4.3 and 11.6.1 in one action.

**Note on 6.4.3**: the requirement asks for three things per script — that it is
*authorized*, that its *integrity is assured*, and that an *inventory with written
business justification* exists. The tool observes; the register is where a human supplies
authorization and justification. Do not let the UI imply the tool can authorize anything.

### 6.2 Scope Map

Renders nested containment — out-of-scope ⊃ connected-to ⊃ CDE — exactly as the mockup
does. Nesting shows containment, **not** network topology; the mockup says so in the
legend and the UI must keep saying it.

- Each zone shows population and open-evidence rollups, computed by joining assets to
  their checklist items.
- Per-system evidence marks (the `•••` in the mockup) are outstanding items on that system.
- A cardholder-data-flow list with an `evidenced` flag per flow. Unevidenced flows are
  called out — the mockup's phone-order flow is the archetype.
- **Confirm scope** freezes an immutable `scope_declaration` version, requires a business
  signatory, and emits a dated scope document + data-flow diagram artifact. That artifact
  is the 12.5.2 evidence, and it is what the drift detector compares against.

### 6.3 Scope Drift Detector

```
  sources                    adapters          normalizer        reconciler
  ─────────────────────      ────────          ──────────        ──────────
  CSV / JSON import   ─┐
  Payment monitor      ├──►  per-source  ──►  canonical    ──►  declared vs   ──► findings
  Cloud read-only APIs │     adapter          asset          observed
  DNS / network disc. ─┘                      identity         rule pack
```

**Adapter contract.** Every source produces `observations` rows with a raw payload and a
declared shape. Adding a source is writing one adapter; nothing downstream changes.

**Normalizer.** Resolves observations to canonical assets by identifier precedence
(cloud resource ID → hostname → IP+time-window → MAC/serial). Unresolvable observations
become candidate new assets, not silent drops.

**Reconciler.** Runs a versioned rule pack over (declared scope version, observation set).
Rule classes, each mapping to the mockup's finding types:
- undeclared network path reaching a CDE system *(1.4.2, 12.5.2 — the dev-sandbox finding)*
- undeclared asset receiving data from a CDE system *(3.2.1, 10.5.1 — the log bucket)*
- declared system no longer observed *(12.5.1 — retire it, shrink the assessment)*
- segmentation test older than the most recent network configuration change *(11.4.5)*
- observed script set ≠ declared script register *(6.4.3 — the internal source)*

Every finding carries a **declared/observed pair**, rendered as the two-column contrast in
the mockup. Dispositions: *open task*, *accept scope* (which creates a new scope
declaration version — accepting drift is a scope change, and must be recorded as one), or
*retire*.

**Sequencing.** File import and the payment-monitor source ship in M5. Cloud connectors
(M7) add credential storage — envelope-encrypted, least-privilege read-only roles,
documented required permissions per provider. DNS/network discovery (M7) is gated behind a
**domain-ownership attestation** the org must sign before any host is touched; the tool
refuses to scan hosts outside attested domains.

### 6.4 PCI Checklist

Seeded `requirement_catalog` for v4.0.1, with per-item *evidence-expected* descriptors.

> **Licensing note.** PCI DSS requirement text is copyrighted by the PCI Security
> Standards Council. We ship requirement **identifiers, titles, and our own paraphrased
> evidence descriptors**, plus a loader that ingests the org's own licensed copy of the
> standard for full text. Do not paste the standard's text into the repo.

**The analyzer** evaluates each item's attached evidence deterministically:
- *cadence* — is the artifact's `collected_at` inside the required window? (ASV quarterly,
  pen test annual, training annual, tamper inspection quarterly)
- *kind* — does the artifact type match what the requirement expects?
- *coverage* — does the config export cover every in-scope system, or only some? Joins
  against the scope map
- *currency* — has a change (network, scope, script) invalidated an otherwise-valid artifact?
- *completeness* — signature present, all four quarters attached, retest included

Output per item: `satisfied | insufficient | missing`, plus specific advice. Gap list
ordered by **assessment risk** = f(blocking, vendor lead time, cadence deadline, days to
walkthrough) — which is why the mockup ranks the ASV scan above items due sooner.

### 6.5 ROC Export

Builds the archive in the general worker, streaming, structured as the mockup shows:

```
<org>-roc-<date>/
  01_roc_template.docx        02_aoc_signed.pdf       03_scope/
  04_evidence/req_01…req_12/  05_scans_and_tests/     06_open_items.csv
  manifest.sha256
```

Options: SHA-256 manifest (default on), redact cardholder data samples (default on),
include superseded versions (default off). **The archive always builds, even incomplete** —
gaps are written into `06_open_items.csv` with owner and due date, so the assessor sees the
same list the engineer does. Result is itself a content-addressed artifact with a signed,
expiring download URL.

---

## 7. The rules engine (and the Coach)

One engine, three consumers: checklist analyzer, drift reconciler, Coach sidebar.

```python
@rule(
    id="R.11.4.3.stale_pentest",
    version="1.0.0",
    requirements=["11.4.3"],
    severity=Severity.BLOCKING,
)
def stale_pentest(ctx: EvidenceGraph) -> Finding | None:
    ...
```

- Rules are **pure functions over an `EvidenceGraph` snapshot**. No I/O, no clock reads —
  `ctx.now` is injected. This makes them trivially unit-testable against fixture graphs.
- Rules packs are **semver-versioned**, and the pack version is stamped on every finding,
  checklist verdict, and generated artifact. Re-running pack `1.2.0` against the same
  evidence six months later yields byte-identical output. That is the whole reason we
  chose deterministic over LLM.
- **Message templates carry named slots**, so copy stays specific without generation:
  `"The report on file is {age_months} months old, which fails {req} on its face."`
- The Coach panel is context-scoped: each route requests findings filtered to its scope,
  grouped into the mockup's three card types — *where you stand* / *do these first* /
  *worth knowing*. It renders findings; it does not compute them.

Every rule needs a fixture-based test before it ships. A wrong rule here tells someone
they are compliant when they are not.

---

## 8. Security posture

This tool holds an organization's compliance evidence and, once cloud connectors land,
read credentials to their environment. It is a security-impacting system for its own users.

- **No cardholder data, ever.** PAN-pattern detection (Luhn-validated) runs on every
  ingested file; matches are quarantined, not stored, and the upload is rejected with a
  specific message. The redaction pass on ROC export is a second net, not the first.
- **Hash-chained audit log** on every state change with actor, target, and prior-entry hash.
- **Secrets** — cloud credentials envelope-encrypted with a KMS key (prod) or a
  file-mounted key (single-tenant self-hosted). Never in environment variables in prod;
  Docker secrets or mounted files only.
- **Crawler isolation** — the Playwright container renders untrusted third-party
  JavaScript. Egress-only network, no database credentials, no object-storage credentials,
  results returned via the queue. Non-root, seccomp default, dropped capabilities.
- **Authorization gate** on DNS/network discovery — see §6.3's domain-ownership
  attestation.
- **RBAC** — at minimum `owner | engineer | auditor(read-only) | viewer`. The auditor role
  matters: you will want to hand an assessor a read-only login.
- The UI must never state a control **is** compliant. It states what evidence exists, what
  is missing, and what a rule found. The determination is the QSA's.

---

## 9. Docker & build configurations

### Images

| Image | Base | Contents |
|---|---|---|
| `web` | `node:22-alpine` → `nginx:alpine` | Vite build → static, nginx with security headers |
| `api` | `python:3.12-slim` | FastAPI, uvicorn, migrations entrypoint |
| `worker` | `python:3.12-slim` | ARQ general worker |
| `worker-crawl` | `mcr.microsoft.com/playwright/python` | ARQ + Chromium |

All multi-stage, non-root, healthchecked, pinned by digest in production.

### Local — `docker-compose.yml` + `compose.override.yml`

Applied automatically by `docker compose up`.

- Postgres 16, Redis 7, MinIO (auto-created bucket), Mailpit
- `api` with `--reload`, source bind-mounted
- `web` running the Vite dev server with HMR, proxying `/api` to `api`
- `worker-crawl` with `PWDEBUG` available and video capture on for crawl debugging
- Seed command loads the requirement catalog and a demo org matching the mockup's
  "Northgate Retail" data, so the UI has something real to render from day one
- One command from clone to running: `make dev`

### Production — `compose.prod.yml`

- Caddy terminating TLS with automatic certificates, serving `web`, proxying `/api`
- Digest-pinned images built in CI, never built on the host
- Migrations as a one-shot job that must exit 0 before `api` starts
- Secrets via Docker secrets / mounted files; `.env` carries only non-sensitive config
- Read-only root filesystems with explicit `tmpfs` mounts; resource limits on every service
- Postgres with a persistent volume and a scheduled `pg_dump` to object storage
- Structured JSON logs to stdout, `/healthz` and `/readyz` on api

### Continuous integration — GitHub Actions

Landed after M0, ahead of the M8 slot it was originally scheduled for (D-0005). The
reasoning: the two gates that matter most (`alembic check` and the tenant-isolation suite)
are worth far more *before* M1 adds four data-plane tables than after.

**`ci.yml`** — pull requests and pushes to `main`. Three jobs, path-filtered by a
`changes` job rather than by `on.*.paths`, so a skipped job still satisfies a required
status check instead of hanging pending.

| Job | Runs | Catches |
|---|---|---|
| `api` | `ruff check src tests alembic`, `ruff format --check`, `mypy src` (strict), `pytest -m "not integration"` | Style and type drift; Python 3.12 skew against a 3.14 laptop |
| `web` | `npm ci`, `eslint`, `tsc --noEmit`, `vite build`, compliance-copy grep | Lockfile drift; type errors; UI copy that asserts compliance |
| `db` | `alembic upgrade head`, single-head check, **`alembic check`**, downgrade/upgrade round trip, `pytest -m integration` | Models and migrations diverging; a data-plane table without RLS, a policy, or a grant |

**`stack.yml`** — backend and infra paths, pushes to `main`, and a weekly cron. Builds
all three images with GHA layer caching, brings up `docker-compose.yml` +
`compose.ci.yml`, and runs `scripts/smoke.sh` against it. This is the only check that
exercises the Dockerfiles, the Postgres init SQL, container ordering, the healthchecks and
the operational CLI together. Deliberately *not* a required check — a frontend-only change
should not wait on it.

Supporting decisions, recorded in `docs/decisions.md` (D-0005):

- **Quality runs natively, not through compose.** The same commands in CI and in
  `make lint` / `make test`, so a green Makefile means something.
- **Dependencies are pinned with hashes** in `apps/api/requirements.txt` (runtime) and
  `requirements-dev.txt` (adds the tooling). Both the images and CI install from them, so
  what CI tests is what ships. `make lock` regenerates; CI fails a PR that edits
  `pyproject.toml` without them.
- **Actions are SHA-pinned**, with Dependabot bumping them weekly across four ecosystems.
- **Secret scanning, push protection and CodeQL belong in repository settings, not in
  workflows.** All three are free on a public repository and need no maintenance, and push
  protection blocks a credential at push time rather than reporting it once it is already
  in public history. *Still to be switched on — Settings → Code security.*

Two other things are deliberately absent. There is no CODEOWNERS: on a one-person
repository it requests review from you, on your own pull request. And there is no coverage
threshold, which would measure very little until the rules engine exists in M3.

Image publishing to GHCR stays in M8 — see the milestone stub in `docs/tasks.md` for what
it still needs.

### Tenancy as a build configuration

A single environment variable, `DEPLOYMENT_MODE=single_tenant|saas`, switches:

| | `single_tenant` | `saas` |
|---|---|---|
| Signup | disabled; first-run admin bootstrap | open, email-verified |
| Org resolution | implicit single org from config | subdomain or JWT claim, middleware-enforced |
| Auth backends | local + optional OIDC | local + OIDC/SAML + org invites |
| Worker queues | shared | per-tenant queue prefix, fair scheduling |
| Rate limits | generous | per-org quotas |
| Secrets | file-mounted key | per-tenant KMS data keys |

The data model, RLS policies, and API surface are **identical** in both. `org_id` is
present and enforced in single-tenant too — the isolation boundary is exercised from day
one rather than bolted on at the point of sale (D-0004).

---

## 10. Repository layout

```
PCI_Tools_Suite/
├── CLAUDE.md                   ← routing protocol pointer for coding sessions
├── Makefile                    ← dev, test, lint, lock, smoke, seed, build
├── docker-compose.yml          base · compose.override.yml (local)
├── compose.prod.yml            compose.ci.yml (CI: real topology, images from the
├── .env.example                workflow rather than built on the runner)
├── .github/
│   ├── workflows/              ci.yml (api · web · db) · stack.yml (build + smoke)
│   ├── dependabot.yml          pip · npm · docker · github-actions, grouped
│   └── pull_request_template.md
├── scripts/smoke.sh            end-to-end assertions against a running stack
├── apps/
│   ├── web/                    React 19 + TS + Vite · eslint.config.js · .nvmrc
│   │   └── src/{routes,components,theme,api-client,lib}
│   └── api/                    Dockerfile.api · Dockerfile.worker
│       ├── requirements.txt        hash-pinned runtime lock (images + CI)
│       ├── requirements-dev.txt    adds pytest, ruff, mypy, uv
│       ├── tests/                  offline suite
│       │   └── integration/        tenant isolation, needs a live Postgres
│       └── src/demarc/
│           ├── api/            routers, deps, schemas
│           ├── core/           config, security, audit
│           ├── db/             models, migrations
│           ├── services/       evidence, scope, checklist, export
│           ├── crawler/        playwright capture + diff
│           ├── drift/          adapters, normalizer, reconciler
│           ├── rules/          versioned packs + engine
│           └── workers/        arq definitions + cron
├── packages/catalog/           PCI DSS v4.0.1 requirement seeds
├── infra/{caddy,postgres}/
└── docs/
    ├── constitution.md         rules that cannot be broken; the routing protocol
    ├── spec.md                 ← this file
    ├── tasks.md                current task breakdown + milestone backlog
    ├── decisions.md            append-only decision log
    └── mockups/                the provided .dc.html + _ds design systems
```

---

## 11. Milestones

The milestone sequence, exit criteria, and the current task breakdown live in
`docs/tasks.md`.

---

## 12. Non-goals and known risks

**Non-goals.** Not an ASV scanner. Not a pen-test tool. Not a compliance determination —
the QSA decides. Does not store cardholder data under any circumstance. Does not remediate;
it observes, compares, and reports.

**Risks to watch.**
1. *Requirement-text licensing* — see §6.4. Paraphrase and load, never paste.
2. *Crawler fidelity* — payment pages behind multi-step flows, bot detection, and
   geo-gating will each break naive crawls. Budget real time in M2 for the navigation-step
   scripting and for detecting when a crawl silently landed on the wrong page.
3. *Asset identity in the normalizer* — the hardest correctness problem in the project.
   Ephemeral cloud IPs and short-lived instances make "is this the same system?" genuinely
   ambiguous. Get the identifier precedence right and make unresolved observations visible
   rather than dropped.
4. *False confidence* — the worst failure mode is telling someone they are covered when
   they are not. Every rule gets fixture tests; the UI states evidence, never compliance.
   The copy half is gated in CI; the rules half becomes a gate in M3.
5. *This tool entering its own scope* — once it holds cloud read credentials it is a
   security-impacting system for its users. §8 is not optional polish.
6. *Gates that pass vacuously* — a test that cannot fail is worse than a missing one,
   because it reads as coverage. Two examples already: the pre-CI schema test compared a
   tuple to a tuple and could not see whether a policy existed; and an obvious-looking
   check of forced RLS via the owner connection proves nothing, because `POSTGRES_USER` is
   a superuser and superusers bypass RLS whatever `FORCE` says. When adding a gate,
   confirm it fails against the broken state before trusting it.

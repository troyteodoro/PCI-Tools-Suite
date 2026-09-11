# Demarc — Decision Log

**Append-only.** This is the record of every decision that changes the project — choices,
assumptions, and corrections of oversights, whether made by the user or by the coding
assistant. The rules (from `docs/constitution.md` §2):

- Entries are **never edited or deleted**. A wrong or outdated decision is superseded by
  a new entry that references it (`Supersedes: D-NNNN`).
- Every change to `docs/spec.md` or `docs/tasks.md` carries an entry recording what
  changed and why.
- Assumptions are never silent. If the assistant has to assume anything, the assumption
  becomes an entry.

Entry format: `## D-NNNN — <title> (YYYY-MM-DD)` with **Context**, **Decision**,
**Consequences**. Numbers are sequential and never reused.

> Entries D-0001 through D-0005 are backfilled from pre-existing documents
> (`docs/prompt.md`, `PLAN.md` §2, ADR 0001, ADR 0002) at restructure time (D-0006),
> dated to when the decisions were originally made.

---

## D-0001 — Project origin: the brief (2026-08-13, backfilled)

**Context.** The project began from two prompts, preserved verbatim here (originally
`docs/prompt.md`). First, the mockup brief:

> Make UI mockups for a pci tool application. the first page should be a dashboard that
> shows current status on pci completion and also list the available tools. there should
> be a page for each tool and a tab bar that references them. Include also a pci coach
> that lives as a side panel. The tools are: 1. a payment page monitor script ( Crawls a
> checkout page, inventories every script and its integrity attributes, snapshots the
> state, alerts on change, and emits a dated evidence artifact. Directly answers
> requirements 6.4.3 and 11.6. ), 2. visual mapping of the items within PCI scope ( this
> maps the cardholder environment and business , as well as provide a visual
> representation of what is left in evidence to provide for pci compliance), 3. scope
> drift detector ( takes declared pci scope and compares it against its observed
> environment and maps contradictions and findings as outout ), 4. pci checklist (
> analyzes evidence and provides advice on what is necessary to add ). Each page should
> display coach advice that is within the context of each tool and the status of the
> project. With the pci checklist page the coach should display an extended list of what
> is displayed on the dashboard of necessary items to add to your pci checklist. An
> additional page should be made for exporting your evidence to an ROC and all necessary
> documents zipped file.

Then, the application brief:

> Lets create a pci tools application. Lets break up the architecture into a frontend
> react application and determine the best backend to use based on the usecase. The
> application hosts a suite of tools that aid the Security Engineer reviewing PCI
> documents for completing their annual PCI validation or companies wanting to reach
> their first pci compliance.
> The Tools:
> - Payment Page Monitor — Crawls a checkout page, inventories every script and its
>   integrity attributes, snapshots the statem alerts on change, and emits a dated
>   evidence artifact. Directly answers requirements for 6.4.3 and 11.6.1
> - visual mapping of the items within PCI scope — this maps the cardholder environment
>   and business , as well as provide a visual representation of what is left in evidence
>   to provide for pci compliance
> - scope drift detector — takes declared pci scope and compares it against its observed
>   environment and maps contradictions and findings as outout
> - pci checklist — analyzes evidence and provides advice on what is necessary to add
>
> Lets dockerize this web application. Lets consider a local and production build
> configuration. Lets start with the frontend. Provided is a claude design ui mockup.

**Decision.** Build the suite as briefed: five tools (the four above plus ROC Export) with
a PCI Coach side panel, React frontend, dockerized with local and production
configurations.

**Consequences.** The delivered mockup (`docs/mockups/`, Modernist + Nocturne) became the
design spec (spec.md §1). The tool set and requirement mapping in spec.md §1/§6 derive
directly from this brief.

---

## D-0002 — Platform and product decisions (2026-08-13, backfilled)

**Context.** The initial planning session locked the platform choices before any code.
Originally recorded as the "Decisions locked" table in PLAN.md §2.

**Decision.**

- **Product name: Demarc.** The telecom demarcation point — where your responsibility
  ends and someone else's begins, which is exactly what a PCI scope boundary is, and
  network/security engineers read it instantly. Short enough for the sidebar at 12.5px.
  *Domain and trademark not yet cleared — do that before any public use.*
- **Backend: Python 3.12 + FastAPI.** Playwright drives the crawler; cloud SDKs (boto3,
  azure, google-cloud) for drift connectors are first-class; strong document/archive
  tooling for ROC export; async throughout.
- **Frontend: React 19 + TypeScript + Vite**, per the brief, with token-driven CSS ported
  from the mockup's design systems.
- **Tenancy: `org_id` in the schema from day one; single-tenant is the first build
  target**, SaaS is a second build configuration over the same core. Single-tenant is
  what a security engineer can get approved to run inside their own environment; carrying
  `org_id` means SaaS is a config flip, not a migration.
- **Drift inputs: all four, sequenced** — file import → payment-monitor internal →
  read-only cloud connectors → DNS/network discovery. File import needs no credentials
  and is demoable immediately; every other source is an adapter behind the same
  normalizer.
- **PCI Coach: deterministic rules engine only, no LLM.** Compliance advice must be
  reproducible and defensible. A versioned rules pack means any statement the tool made
  six months ago can be re-derived exactly. No API key, no network dependency, no
  hallucinated compliance claims.

**Consequences.** These choices shaped spec.md §3 (architecture), §7 (rules engine), and
§9 (tenancy as a build configuration). They are locked; superseding any of them requires
a new entry approved by the user.

---

## D-0003 — M0 assumptions made without asking (2026-08-13, backfilled)

**Context.** Three gaps in the brief were filled by assumption during initial planning
rather than by asking. Originally recorded in PLAN.md §2 under "Assumptions made without
asking".

**Decision.**

- **Auth**: local accounts (argon2id, session cookies, TOTP-capable) with RBAC in the
  single-tenant build. OIDC/SAML added in the SaaS build configuration.
- **Theme**: both Modernist and Nocturne ship in every build as a runtime user
  preference, not a build-time flag. They are pure CSS custom-property swaps.
- **Standard version**: PCI DSS v4.0.1 only. The catalog is versioned so v4.1 can be
  loaded alongside without a migration.

**Consequences.** M0 implemented all three. Under the constitution now in force,
assumptions of this kind must be logged here at the moment they are made.

---

## D-0004 — Tenant isolation: two planes, one enforced by the database (2026-08-17, backfilled from ADR 0001)

**Context.** D-0002 commits to carrying `org_id` from day one so the SaaS build
configuration is a config flip rather than a migration, and spec.md §9 says the isolation
boundary should be exercised in single-tenant too rather than introduced at the point of
sale.

Application-level filtering (`WHERE org_id = :org`) is one forgotten clause away from
cross-tenant disclosure. For a product whose entire value is holding an organization's
compliance evidence, that is not an acceptable single point of failure.

Postgres row-level security gives us a second, independent enforcement point. But RLS
cannot protect the tables that *establish* who you are — resolving a session token
requires reading `sessions` before any tenant context exists.

**Decision.** Split the schema into two planes.

**Auth plane** — `organizations`, `users`, `memberships`, `sessions`. No RLS. These are
the mechanism that establishes tenancy and so cannot depend on it. Access is confined to
`demarc.services.auth`, which always filters by organization explicitly. This is a small,
reviewable surface.

**Data plane** — every table holding compliance data, starting with `audit_log` and
growing to artifacts, assets, findings, snapshots and the rest. `ENABLE ROW LEVEL
SECURITY` and `FORCE ROW LEVEL SECURITY`, with a policy keyed on the transaction-local
setting `demarc.org_id`.

The runtime connects as `demarc_app`, which:

- is **not** the table owner (owners bypass RLS unless forced; we force it anyway)
- has no `BYPASSRLS` attribute
- holds only `SELECT, INSERT, UPDATE, DELETE` on the tables it needs

Tenant context is set with `set_config('demarc.org_id', $1, true)`. The `true` makes it
transaction-local, so a connection handed back to the pool never carries a previous
request's tenant.

The policy compares against `nullif(current_setting('demarc.org_id', true), '')::uuid`,
and the `nullif` is load-bearing rather than defensive. A transaction-local setting does
not revert to `NULL` when the transaction ends — it reverts to the empty string, and
`''::uuid` raises. Without it, a data-plane query with no tenant context returns zero rows
on a fresh connection and raises `invalid input syntax for type uuid` on a recycled one.
Since the pool recycles constantly, the recycled path is the normal one. The failure is
closed either way, but "fail closed and quietly" is the behaviour this decision promises,
and a 500 is neither quiet nor predictable.

`audit_log` additionally has no `UPDATE` or `DELETE` grant at all. It is append-only in
the database, not merely by convention.

**Consequences.**

- A data-plane query that forgets its `org_id` filter returns zero rows instead of
  another tenant's evidence. Both enforcement points have to fail simultaneously to leak.
- Every data-plane query must run inside `org_session()`. Using `auth_session()` for
  domain data returns nothing — a loud, immediate failure rather than a silent one.
- Migrations run as the owner role, the application as `demarc_app`. Two roles to manage.
- `FORCE` constrains the table *owner*, not a superuser: `POSTGRES_USER` is created a
  superuser by the Postgres image in every configuration, and superusers bypass RLS
  unconditionally. So `FORCE` is what protects an accidental owner-role query in a
  migration or a maintenance script, and the fact that the runtime role is separate,
  non-owner, and has no `BYPASSRLS` is what protects everything else. Neither alone is
  sufficient. This also means a test that probes isolation over an owner connection is
  measuring nothing — see D-0005.
- Adding a data-plane table means adding it to `DATA_PLANE_TABLES` **and** applying the
  policy in a migration. `tests/integration/test_tenant_isolation.py` is parametrized
  over `DATA_PLANE_TABLES` and runs against a live Postgres, so a table missing RLS,
  `FORCE`, a policy or a grant fails CI rather than shipping — with no new test to write
  per table. (`tests/test_schema_invariants.py` parses the migration and catches a table
  declared on the wrong plane; it cannot see whether any of the above was actually
  applied. The two are complements, not duplicates.)
- The auth plane is protected by code review and a narrow module boundary, not by the
  database. That is a real, accepted limitation, and it is why user enumeration and
  membership lookups are confined to one file.

---

## D-0005 — CI gates: what blocks a merge, and why it came before M1 (2026-08-17, backfilled from ADR 0002)

**Context.** The original milestone plan scheduled CI image builds and the
tenant-isolation test suite for M8, the last milestone. That ordering made sense when
read as "release engineering", and stopped making sense once M1's shape was clear.

M1 adds four data-plane tables. Every one is an opportunity to forget an RLS policy, a
`FORCE`, or a `GRANT`, and the failure mode of forgetting is not a broken build — it is a
runtime 500 at best and a cross-tenant read at worst. D-0004 already assumed this suite
existed. It did not exist.

The pre-existing checks could not cover it. `tests/test_schema_invariants.py` parses the
migration with `ast` and compares a tuple to a tuple. That catches a table declared on the
wrong plane and nothing else — not whether the policy was created, not whether `FORCE` was
applied, not whether `demarc_app` was granted anything. Those are properties of a running
database.

Standing the gates up confirmed the concern was not hypothetical. Five defects existed in
a repository that looked clean, and each was invisible to every check that ran at the
time. They are listed under Consequences.

**Decision.** Bring CI forward to sit between M0 and M1 (as "M0.5"), and scope it to
gates rather than release. Image publishing stays in M8: there is no deployment target
yet, and `compose.prod.yml` cannot express digest pinning until its `image:` lines change
form. Publishing images nobody pulls would be ceremony with a credential surface attached.

- **Two workflows.** `ci.yml` gates every pull request with three path-filtered jobs —
  `api` (ruff, mypy strict, offline pytest), `web` (eslint, tsc, vite build), `db`
  (migrations and tenant isolation against a real Postgres). `stack.yml` builds the three
  images and runs `scripts/smoke.sh` against the composed deployment; it is path-filtered
  and not required, because a frontend-only change should not wait eight minutes for it.
- **Path filtering happens in a `changes` job, not in `on.*.paths`.** A workflow that
  never triggers leaves its required status checks pending forever, and the pull request
  cannot be merged. A job skipped by `if:` reports as skipped, which GitHub counts as
  satisfied.
- **Quality tooling runs natively, not through compose.** The previous `make test` and
  `make lint` could not work at all: `Dockerfile.api` never copies `tests/`, the
  container runs as uid 10001 so an in-container `pip install` is denied, and the `web`
  service exists only in the local override. Running the same commands locally and in CI
  means a green `make lint` carries information.
- **Dependencies are hash-pinned in `requirements.txt` (runtime) and
  `requirements-dev.txt` (adds tooling), generated by `make lock`.** The images install
  from the same runtime lock CI tests against, so the two cannot drift. Previously the
  images resolved `>=` ranges at build time, meaning a green CI run said nothing about
  what the image contained. A PR that edits `pyproject.toml` without regenerating fails;
  re-resolving in CI instead would fail on any upstream release, which is a flake, not a
  gate.
- **mypy strict is a hard gate from day one.** It was configured and had never run. An
  advisory job that is permanently yellow gets ignored within a week. The first run
  produced nine errors, all fixed.
- **Secret scanning, push protection and CodeQL are repository settings, not workflows.**
  They are free on a public repository, and push protection blocks a credential *at push
  time* rather than reporting it after it is already in public history. gitleaks waits
  for M7: the repository deliberately contains development credentials that a generic
  entropy scanner flags on every run, and cloud connector keys are what make a custom
  ruleset worth writing.

**Consequences.**

- A pull request cannot merge with a data-plane table missing RLS, a policy, or a grant.
  `tests/integration/test_tenant_isolation.py` is parametrized over `DATA_PLANE_TABLES`,
  so M1–M7 tables are covered on registration with no new test to remember.
- `alembic check` means migrations may no longer be hand-edited to approximate the
  models. Use `make revision M="…"`.
- Two test tiers now exist. The offline suite stays offline: everything under
  `tests/integration/` is auto-marked, and the default run is `-m "not integration"`.
- Dependency changes are a two-file operation. `make lock` after `pyproject.toml`, always.
- The smoke script is checked in rather than inlined in YAML, so `make smoke` runs the
  same assertions against a local `make dev` stack.

**Defects the gates surfaced immediately**, none of which any prior check could see:

1. *Models and migrations disagreed.* `users.email`, `organizations.slug` and
   `sessions.token_hash` are declared `unique=True, index=True`, which SQLAlchemy renders
   as a single unique index. The migration created a `UniqueConstraint` plus a separate
   non-unique index — so the database carried three redundant indexes and `alembic check`
   failed on all three.
2. *The RLS policy raised instead of returning zero rows.* A transaction-local
   `set_config` reverts to the empty string, not to `NULL`, so
   `current_setting('demarc.org_id', true)::uuid` raised `invalid input syntax for type
   uuid` on any connection that had previously served a request. With a pool, that is the
   common path, not an edge case. It failed closed, so nothing leaked — but the
   documented contract is "returns nothing", and it returned a 500. Fixed with
   `nullif(…, '')` in the policy, which every future data-plane table inherits.
3. *`minio-init` existed only in `compose.override.yml`*, so production had MinIO with no
   evidence bucket and no versioning. Invisible at M0 because nothing used object storage
   yet; it would have surfaced in M1.
4. *`make test` and `make lint` could not run*, for the reasons above.
5. *`npm ci … || npm install`* in the web Dockerfile meant the image build could never
   fail on lockfile drift, which is the single thing `npm ci` exists to catch.

**A gate that cannot fail is worse than a missing one.** The obvious-looking probe for
`FORCE ROW LEVEL SECURITY` — count rows on an owner connection and expect zero — proves
nothing here: `POSTGRES_USER` is created a superuser by the Postgres entrypoint, and
superusers bypass RLS regardless of `FORCE`. On an empty table it would also have passed
vacuously. The smoke script therefore asserts the catalog flags directly, asserts that
`demarc_app` is neither superuser nor `BYPASSRLS`, and runs the behavioural probe as
`demarc_app` after seeding, when there is something to hide. Every new gate should be
confirmed to fail against the broken state before it is trusted — now constitution §2.3;
see also spec.md §12 risk 6.

---

## D-0006 — Restructure to spec-driven / task-driven development (2026-09-10)

**Context.** With M0 and M0.5 complete and M1 about to add the evidence spine, the user
chose to restructure the project's documentation from a single PLAN.md into a
four-document SDD/TDD system, so that every coding session routes through fixed documents
and every decision is durably logged.

**Decision.** Adopt the four-document system with the routing protocol
(constitution → current task → referenced spec sections + decision entries → work),
including these sub-decisions made explicitly by the user:

1. `docs/PLAN.md` is deleted after full absorption into the four documents; git history
   preserves it.
2. The ADRs are folded into this log (D-0004, D-0005) and `docs/adr/` is deleted — one
   decision document.
3. `docs/tasks.md` details only the current milestone; later milestones remain ordered
   stubs with exit criteria, decomposed when they become current.
4. **TDD is risk-tiered**: strict test-first (failing test before implementation) for the
   rules engine, tenant isolation, evidence immutability, PAN detection, and the audit
   hash chain; everywhere else, tests land in the same commit/PR, and every new gate must
   be shown to fail against the broken state before it is trusted.
5. Each of the five restructure steps (constitution, spec, decisions, tasks, CLAUDE.md
   integration) got its own plan-mode approval cycle.
6. `docs/prompt.md` is folded into this log as D-0001, then deleted.
7. The constitution includes four agent-governance rules: git discipline (no commit/push
   without explicit request, feature branches only), verification before done, no scope
   creep, and constitution self-protection (user-approved amendments only).
8. `docs/spec.md` preserves PLAN.md's section numbering (moved sections become pointer
   stubs) so existing `PLAN.md §N` citations in code and CI translate mechanically.

**Consequences.** `docs/constitution.md`, `docs/spec.md`, this log, and `docs/tasks.md`
now exist; `CLAUDE.md` is rewritten to enforce the routing protocol; `docs/PLAN.md`,
`docs/prompt.md`, and `docs/adr/` are deleted in the integration step, after their
content is verified present here and in spec.md; all `PLAN.md §N` citations in code, CI,
and README are updated to `docs/spec.md §N` (or `docs/tasks.md` for the milestone
sequence). This log is the only decision record going forward.

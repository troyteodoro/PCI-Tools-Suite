# ADR 0001 — Tenant isolation: two planes, one enforced by the database

Status: accepted (M0)

## Context

PLAN.md §2 commits to carrying `org_id` from day one so the SaaS build configuration is a
config flip rather than a migration, and §9 says the isolation boundary should be
exercised in single-tenant too rather than introduced at the point of sale.

Application-level filtering (`WHERE org_id = :org`) is one forgotten clause away from
cross-tenant disclosure. For a product whose entire value is holding an organization's
compliance evidence, that is not an acceptable single point of failure.

Postgres row-level security gives us a second, independent enforcement point. But RLS
cannot protect the tables that *establish* who you are — resolving a session token
requires reading `sessions` before any tenant context exists.

## Decision

Split the schema into two planes.

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
closed either way, but "fail closed and quietly" is the behaviour this ADR promises, and a
500 is neither quiet nor predictable.

`audit_log` additionally has no `UPDATE` or `DELETE` grant at all. It is append-only in
the database, not merely by convention.

## Consequences

- A data-plane query that forgets its `org_id` filter returns zero rows instead of another
  tenant's evidence. Both enforcement points have to fail simultaneously to leak.
- Every data-plane query must run inside `org_session()`. Using `auth_session()` for
  domain data returns nothing — a loud, immediate failure rather than a silent one.
- Migrations run as the owner role, the application as `demarc_app`. Two roles to manage.
- `FORCE` constrains the table *owner*, not a superuser: `POSTGRES_USER` is created a
  superuser by the Postgres image in every configuration, and superusers bypass RLS
  unconditionally. So `FORCE` is what protects an accidental owner-role query in a
  migration or a maintenance script, and the fact that the runtime role is separate,
  non-owner, and has no `BYPASSRLS` is what protects everything else. Neither alone is
  sufficient. This also means a test that probes isolation over an owner connection is
  measuring nothing — see ADR 0002.
- Adding a data-plane table means adding it to `DATA_PLANE_TABLES` **and** applying the
  policy in a migration. `tests/integration/test_tenant_isolation.py` is parametrized over
  `DATA_PLANE_TABLES` and runs against a live Postgres, so a table missing RLS, `FORCE`, a
  policy or a grant fails CI rather than shipping — with no new test to write per table.
  (`tests/test_schema_invariants.py` parses the migration and catches a table declared on
  the wrong plane; it cannot see whether any of the above was actually applied. The two
  are complements, not duplicates.)
- The auth plane is protected by code review and a narrow module boundary, not by the
  database. That is a real, accepted limitation, and it is why user enumeration and
  membership lookups are confined to one file.

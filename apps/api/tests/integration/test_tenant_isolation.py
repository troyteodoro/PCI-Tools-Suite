"""The tenant-isolation boundary, asserted against a running Postgres.

`tests/test_schema_invariants.py` compares a Python tuple against a tuple parsed out of
the migration. That catches a table declared on the wrong plane, but it cannot see
whether the policy was actually created, whether FORCE was applied, or whether the
runtime role was granted anything. Those are properties of a live database, so they are
tested here (docs/adr/0001-tenant-isolation.md).

Most of the file is parametrized over `DATA_PLANE_TABLES`, so a table added in any later
milestone is covered the moment it is registered — no new test to remember to write.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from demarc.db.models import DATA_PLANE_TABLES
from demarc.db.session import current_org_setting, org_session
from demarc.services import audit

APP_ROLE = "demarc_app"


# --------------------------------------------------------------- catalog-level guarantees


@pytest.mark.parametrize("table", DATA_PLANE_TABLES)
async def test_rls_is_enabled_and_forced(owner_conn: AsyncConnection, table: str) -> None:
    """FORCE is the half people forget. Without it the owner bypasses the policy, and
    every migration or maintenance script becomes a cross-tenant read."""
    row = (
        await owner_conn.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class"
                " WHERE relname = :t AND relkind = 'r'"
            ),
            {"t": table},
        )
    ).one()
    assert row.relrowsecurity, f"{table} is on the data plane without RLS enabled"
    assert row.relforcerowsecurity, f"{table} has RLS but not FORCE — the owner bypasses it"


@pytest.mark.parametrize("table", DATA_PLANE_TABLES)
async def test_a_tenant_isolation_policy_exists(owner_conn: AsyncConnection, table: str) -> None:
    policies = (
        (
            await owner_conn.execute(
                text("SELECT policyname FROM pg_policies WHERE tablename = :t"),
                {"t": table},
            )
        )
        .scalars()
        .all()
    )
    assert policies, f"{table} has RLS enabled but no policy, so it returns nothing to anyone"


@pytest.mark.parametrize("table", DATA_PLANE_TABLES)
async def test_the_policy_keys_on_the_org_setting(owner_conn: AsyncConnection, table: str) -> None:
    """A policy that does not reference `demarc.org_id` is not isolating on tenancy,
    whatever it is doing."""
    quals = (
        (
            await owner_conn.execute(
                text(
                    "SELECT coalesce(qual, '') || ' ' || coalesce(with_check, '')"
                    " FROM pg_policies WHERE tablename = :t"
                ),
                {"t": table},
            )
        )
        .scalars()
        .all()
    )
    assert any("demarc.org_id" in q for q in quals), (
        f"no policy on {table} references current_setting('demarc.org_id')"
    )


@pytest.mark.parametrize("table", DATA_PLANE_TABLES)
async def test_the_runtime_role_can_reach_the_table(
    owner_conn: AsyncConnection, table: str
) -> None:
    """The forgotten GRANT. RLS is irrelevant if the app cannot select at all; this
    surfaces as a 500 at runtime rather than as a policy problem."""
    can_select = (
        await owner_conn.execute(
            text("SELECT has_table_privilege(:role, :t, 'SELECT')"),
            {"role": APP_ROLE, "t": table},
        )
    ).scalar_one()
    assert can_select, f"{APP_ROLE} has no SELECT on {table}"


async def test_audit_log_is_append_only_by_grant(owner_conn: AsyncConnection) -> None:
    """Append-only in the database, not by convention. Asserted on the grant rather than
    on the service, so it survives any refactor of demarc.services.audit."""
    for privilege in ("UPDATE", "DELETE"):
        held = (
            await owner_conn.execute(
                text("SELECT has_table_privilege(:role, 'audit_log', :p)"),
                {"role": APP_ROLE, "p": privilege},
            )
        ).scalar_one()
        assert not held, f"{APP_ROLE} holds {privilege} on audit_log — the chain is rewritable"


# ------------------------------------------------------------------- behavioural isolation


async def _record_for(org_id: uuid.UUID, action: str) -> None:
    async with org_session(org_id) as session:
        await audit.record(session, org_id=org_id, action=action, actor_label="test")


async def test_one_org_cannot_see_anothers_rows(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """The actual claim the product makes."""
    org_a, org_b = two_orgs
    await _record_for(org_a, "org.a.event")
    await _record_for(org_b, "org.b.event")
    await _record_for(org_b, "org.b.second")

    assert await _count_visible(org_a) == 1
    assert await _count_visible(org_b) == 2

    async with org_session(org_a) as session:
        actions = (await session.execute(text("SELECT action FROM audit_log"))).scalars().all()
    assert actions == ["org.a.event"], "org A saw rows it does not own"


async def _count_visible(org_id: uuid.UUID) -> int:
    async with org_session(org_id) as session:
        return (await session.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()


async def test_no_tenant_context_returns_nothing_rather_than_erroring(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """A query that forgets its org context must fail closed and *quietly*, on a fresh
    connection and on a recycled one alike.

    The recycled case is the one that regressed: a transaction-local `set_config` reverts
    to the empty string, not to NULL, so a policy comparing
    `current_setting(...)::uuid` raises rather than matching nothing. Because the pool
    recycles constantly, that path is the common one in production, which is why this
    test runs the query *after* an org-scoped transaction on the same pool.
    """
    from demarc.db.session import auth_session

    org_a, _ = two_orgs
    await _record_for(org_a, "org.a.event")  # leaves '' behind on the pooled connection

    for _ in range(3):
        async with auth_session() as session:
            assert await current_org_setting(session) in (None, "")
            count = (await session.execute(text("SELECT count(*) FROM audit_log"))).scalar_one()
        assert count == 0, "rows were visible with no tenant context set"


async def test_inserting_another_orgs_row_is_rejected(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """WITH CHECK, not just USING. Without it a tenant can write into another tenant's
    partition even though it cannot read it back."""
    org_a, org_b = two_orgs
    async with org_session(org_a) as session:
        with pytest.raises(DBAPIError):
            await session.execute(
                text(
                    "INSERT INTO audit_log"
                    " (id, org_id, seq, at, actor_label, action, detail, prev_hash, hash)"
                    " VALUES (:id, :org, 1, now(), 'test', 'smuggled', '{}'::jsonb,"
                    " repeat('0', 64), repeat('1', 64))"
                ),
                {"id": uuid.uuid4(), "org": org_b},
            )


async def test_context_does_not_leak_across_pooled_connections(
    two_orgs: tuple[uuid.UUID, uuid.UUID],
) -> None:
    """`set_config(..., is_local => true)` is transaction-scoped. If it were session-scoped
    a connection returned to the pool would carry one tenant's context into the next
    request — the failure mode that makes pooling and RLS dangerous together."""
    org_a, org_b = two_orgs
    await _record_for(org_a, "org.a.event")

    # Cycle enough transactions to be reasonably sure of reusing a pooled connection.
    for _ in range(5):
        async with org_session(org_b) as session:
            assert (await session.execute(text("SELECT count(*) FROM audit_log"))).scalar_one() == 0

        from demarc.db.session import auth_session

        async with auth_session() as session:
            assert await current_org_setting(session) in (None, ""), (
                "a pooled connection carried demarc.org_id out of its transaction"
            )


async def test_the_chain_verifies_per_org(two_orgs: tuple[uuid.UUID, uuid.UUID]) -> None:
    """verify_chain re-derives hashes through the same RLS-scoped session the API uses,
    so this also proves the chain is reachable under the policy."""
    org_a, org_b = two_orgs
    for action in ("first", "second", "third"):
        await _record_for(org_a, f"a.{action}")
    await _record_for(org_b, "b.only")

    for org_id, expected in ((org_a, 3), (org_b, 1)):
        async with org_session(org_id) as session:
            result = await audit.verify_chain(session, org_id=org_id)
        assert result.ok, f"chain for {org_id} failed: {result.reason}"
        assert result.entries_checked == expected

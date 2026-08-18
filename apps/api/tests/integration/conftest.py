"""Fixtures for tests that need a live Postgres with migrations applied.

Everything here is marked `integration` automatically, so the offline unit run
(`pytest -m "not integration"`) stays offline no matter what lands in this directory.

Two engines, because the point of the suite is that the two roles differ:

* `owner_engine` connects as the migration/owner role. It is how we inspect the
  catalog (`pg_class`, `pg_policies`, grants) and how we plant rows for more than
  one tenant. FORCE ROW LEVEL SECURITY applies to the owner too, so it is not a
  way around the policy.
* the application path goes through `demarc.db.session`, unchanged, so these tests
  exercise the same `org_session()` the API uses rather than a copy of it.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from demarc.db.session import dispose_engine

# Mirrors the compose/CI wiring. Defaults match compose.override.yml's published port
# so the suite is runnable against `make dev` without extra environment.
OWNER_URL = os.environ.get(
    "DEMARC_MIGRATION_DATABASE_URL",
    "postgresql+asyncpg://demarc:demarc@localhost:5432/demarc",
)


_HERE = Path(__file__).parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark everything in this package, so no one has to remember to.

    The hook is handed every collected item, not only this directory's, so it filters
    on path — otherwise it would mark the offline suite as integration too and
    `-m "not integration"` would select nothing.
    """
    for item in items:
        if _HERE in item.path.parents:
            item.add_marker(pytest.mark.integration)


@pytest_asyncio.fixture
async def owner_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(OWNER_URL, connect_args={"statement_cache_size": 0})
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def owner_conn(owner_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with owner_engine.connect() as conn:
        yield conn


@pytest_asyncio.fixture(autouse=True)
async def _reset_app_engine() -> AsyncIterator[None]:
    """`demarc.db.session` memoises its engine in a module global. Disposing it around
    every test keeps one test's pooled connections from carrying into the next, which is
    exactly the leak `test_context_does_not_leak_across_pooled_connections` asserts about.
    """
    await dispose_engine()
    yield
    await dispose_engine()


@pytest_asyncio.fixture
async def two_orgs(owner_engine: AsyncEngine) -> AsyncIterator[tuple[uuid.UUID, uuid.UUID]]:
    """Two organizations that exist for the duration of one test, then are removed.

    Created through the owner because `organizations` is auth-plane (no RLS); the
    interesting assertions are about what the *runtime* role can see afterwards.
    """
    a, b = uuid.uuid4(), uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    async with owner_engine.begin() as conn:
        for org_id, slug in ((a, f"org-a-{suffix}"), (b, f"org-b-{suffix}")):
            await conn.execute(
                text(
                    "INSERT INTO organizations (id, slug, name, merchant_level, saq_type)"
                    " VALUES (:id, :slug, :name, 'level_4', 'a_ep')"
                ),
                {"id": org_id, "slug": slug, "name": slug},
            )
    try:
        yield a, b
    finally:
        # ON DELETE CASCADE takes the audit rows with it.
        async with owner_engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM organizations WHERE id = ANY(:ids)"),
                {"ids": [a, b]},
            )

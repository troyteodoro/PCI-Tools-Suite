"""Async engine and the org-scoped session context.

Two planes, deliberately (see docs/adr/0001-tenant-isolation.md):

* **Auth plane** — `organizations`, `users`, `memberships`, `sessions`. No RLS: these are
  the mechanism that establishes tenancy, so they cannot depend on it. Always queried
  with an explicit org filter in `demarc.services.auth`.
* **Data plane** — every table holding compliance data. RLS enabled and FORCED, keyed on
  the `demarc.org_id` setting. A query that forgets its org filter returns nothing rather
  than another tenant's evidence.

`auth_session()` opens a transaction with no org context. `org_session()` sets the
setting transaction-locally, so it cannot leak across pooled connections.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from demarc.core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

ORG_SETTING = "demarc.org_id"


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(
            str(settings.database_url),
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=10,
            # Statement cache must be off when a pooler sits in front of Postgres;
            # harmless otherwise and saves a confusing class of production bug.
            connect_args={"statement_cache_size": 0},
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


@asynccontextmanager
async def auth_session() -> AsyncIterator[AsyncSession]:
    """A transaction with no tenant context. Auth-plane tables only."""
    async with get_sessionmaker()() as session, session.begin():
        yield session


@asynccontextmanager
async def org_session(org_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A transaction scoped to one organization.

    `set_config(..., is_local => true)` binds the setting to this transaction, so a
    connection returned to the pool never carries another tenant's context.
    """
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(
            text("SELECT set_config(:key, :value, true)"),
            {"key": ORG_SETTING, "value": str(org_id)},
        )
        yield session


async def current_org_setting(session: AsyncSession) -> str | None:
    """Read back the active tenant context. Used by the isolation tests."""
    result = await session.execute(text("SELECT current_setting(:key, true)"), {"key": ORG_SETTING})
    return result.scalar_one_or_none()

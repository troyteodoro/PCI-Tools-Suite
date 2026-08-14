"""Request dependencies: settings, identity, and the org-scoped database session."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from demarc.core.config import Settings, get_settings
from demarc.core.errors import AuthenticationError
from demarc.db.models.user import Role
from demarc.db.session import auth_session, org_session
from demarc.services import auth as auth_service
from demarc.services.auth import AuthContext


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


def client_ip(request: Request) -> str | None:
    """Client address.

    Behind the production reverse proxy uvicorn is run with --proxy-headers, so
    `request.client` already reflects X-Forwarded-For. We deliberately do not parse that
    header here — trusting it unconditionally would let a client forge its own address
    in the audit log.
    """
    return request.client.host if request.client else None


async def current_auth(request: Request, settings: SettingsDep) -> AuthContext:
    """Resolve the session cookie to an identity, or raise 401."""
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise AuthenticationError("Not signed in.")

    async with auth_session() as session:
        context = await auth_service.resolve_session(session, settings=settings, token=token)

    if context is None:
        raise AuthenticationError("Session is invalid or has expired.")
    return context


AuthDep = Annotated[AuthContext, Depends(current_auth)]


async def current_auth_optional(request: Request, settings: SettingsDep) -> AuthContext | None:
    try:
        return await current_auth(request, settings)
    except AuthenticationError:
        return None


OptionalAuthDep = Annotated[AuthContext | None, Depends(current_auth_optional)]


async def org_db(auth: AuthDep) -> AsyncIterator[AsyncSession]:
    """A transaction scoped to the caller's organization.

    Every data-plane query must come through here. RLS returns nothing without it.
    """
    async with org_session(auth.org_id) as session:
        yield session


OrgDbDep = Annotated[AsyncSession, Depends(org_db)]


def require_role(minimum: Role):  # noqa: ANN201 - FastAPI dependency factory
    """Route guard. `require_writable` is separate because read-only roles (auditor,
    viewer) are about intent, not rank — a QSA outranks nobody but must not edit evidence.
    """

    async def _guard(auth: AuthDep) -> AuthContext:
        auth.require(minimum)
        return auth

    return _guard


def require_writer():  # noqa: ANN201
    async def _guard(auth: AuthDep) -> AuthContext:
        auth.require_writable()
        return auth

    return _guard

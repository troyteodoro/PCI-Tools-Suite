"""Auth-plane operations.

This is the *only* module permitted to query `users`, `memberships`, `sessions` and
`organizations` without a tenant context (docs/adr/0001). Every query here filters by
organization explicitly. Keep this file small and keep it reviewed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from demarc.core.config import Settings
from demarc.core.errors import AuthenticationError, BootstrapClosedError, ConflictError
from demarc.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    verify_password,
)
from demarc.db.models.organization import MerchantLevel, Organization, SAQType
from demarc.db.models.session import Session as SessionModel
from demarc.db.models.user import Membership, Role, User

# Verifying against a throwaway hash when the account does not exist keeps the failure
# path the same shape as the success path, so response time does not disclose whether an
# email is registered.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


@dataclass(frozen=True)
class AuthContext:
    """Resolved identity for one request."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    session_id: uuid.UUID
    email: str
    full_name: str
    role: Role

    @property
    def actor_label(self) -> str:
        return self.email

    def require(self, minimum: Role) -> None:
        from demarc.core.errors import PermissionDeniedError

        if not self.role.at_least(minimum):
            raise PermissionDeniedError(
                f"This action requires the {minimum.value} role; you have {self.role.value}."
            )

    def require_writable(self) -> None:
        from demarc.core.errors import PermissionDeniedError

        if self.role.is_read_only:
            raise PermissionDeniedError(
                f"The {self.role.value} role is read-only. Evidence cannot be altered from it."
            )


# --------------------------------------------------------------------------- orgs


async def get_org_by_slug(session: AsyncSession, slug: str) -> Organization | None:
    return (
        await session.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()


async def resolve_login_org(
    session: AsyncSession, settings: Settings, requested_slug: str | None
) -> Organization:
    """Which organization is this login against?

    Single-tenant: always the configured one, whatever the client asked for.
    SaaS: the requested slug (supplied by subdomain or the login form).
    """
    slug = requested_slug if settings.is_saas else settings.single_tenant_org_slug
    if not slug:
        raise AuthenticationError("No organization specified.")
    org = await get_org_by_slug(session, slug)
    if org is None:
        raise AuthenticationError("Invalid credentials.")
    return org


# --------------------------------------------------------------------------- login


async def authenticate(
    session: AsyncSession, *, org: Organization, email: str, password: str
) -> tuple[User, Membership]:
    """Verify credentials and membership. Raises `AuthenticationError` on any failure.

    The message is identical for unknown email, wrong password, deactivated account and
    absent membership — the caller should not learn which.
    """
    normalized = email.strip().lower()
    user = (
        await session.execute(select(User).where(func.lower(User.email) == normalized))
    ).scalar_one_or_none()

    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise AuthenticationError("Invalid credentials.")

    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid credentials.")

    if not user.is_active:
        raise AuthenticationError("Invalid credentials.")

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == user.id, Membership.org_id == org.id
            )
        )
    ).scalar_one_or_none()

    if membership is None:
        raise AuthenticationError("Invalid credentials.")

    # Transparently upgrade the hash if the cost parameters have moved on.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(UTC)
    return user, membership


async def create_session(
    session: AsyncSession,
    *,
    settings: Settings,
    user: User,
    org: Organization,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, SessionModel]:
    """Issue a session. Returns the plaintext token (shown once) and the stored row."""
    token = generate_session_token()
    now = datetime.now(UTC)

    record = SessionModel(
        org_id=org.id,
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
    )
    session.add(record)
    await session.flush()
    return token, record


async def resolve_session(
    session: AsyncSession, *, settings: Settings, token: str
) -> AuthContext | None:
    """Validate a session token and load the identity behind it.

    Returns None for absent, revoked, expired or idle-timed-out sessions. Touches
    `last_seen_at` on success, which is what drives the idle timeout.
    """
    record = (
        await session.execute(
            select(SessionModel).where(SessionModel.token_hash == hash_session_token(token))
        )
    ).scalar_one_or_none()

    if record is None or record.revoked_at is not None:
        return None

    now = datetime.now(UTC)
    if record.expires_at <= now:
        return None

    idle_limit = timedelta(minutes=settings.session_idle_timeout_minutes)
    if now - record.last_seen_at > idle_limit:
        record.revoked_at = now
        return None

    membership = (
        await session.execute(
            select(Membership).where(
                Membership.user_id == record.user_id, Membership.org_id == record.org_id
            )
        )
    ).scalar_one_or_none()

    # Membership revoked mid-session: the session dies with it.
    if membership is None:
        record.revoked_at = now
        return None

    user = (
        await session.execute(select(User).where(User.id == record.user_id))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        record.revoked_at = now
        return None

    record.last_seen_at = now

    return AuthContext(
        user_id=user.id,
        org_id=record.org_id,
        session_id=record.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
    )


async def revoke_session(session: AsyncSession, *, token: str) -> uuid.UUID | None:
    record = (
        await session.execute(
            select(SessionModel).where(SessionModel.token_hash == hash_session_token(token))
        )
    ).scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        return None
    record.revoked_at = datetime.now(UTC)
    return record.org_id


# --------------------------------------------------------------------------- bootstrap


async def deployment_is_bootstrapped(session: AsyncSession) -> bool:
    count = (await session.execute(select(func.count()).select_from(User))).scalar_one()
    return count > 0


async def bootstrap_deployment(
    session: AsyncSession,
    *,
    settings: Settings,
    org_name: str,
    org_slug: str | None,
    email: str,
    full_name: str,
    password: str,
    merchant_level: MerchantLevel = MerchantLevel.UNDECLARED,
    saq_type: SAQType = SAQType.D_MERCHANT,
) -> tuple[Organization, User]:
    """First-run setup: create the organization and its owner.

    Only available while the deployment has no users. There is no bootstrap token to
    leak and no default credential to forget to change — the window closes the moment
    the first account exists.
    """
    if await deployment_is_bootstrapped(session):
        raise BootstrapClosedError()

    slug = (org_slug or settings.single_tenant_org_slug).strip().lower()
    if not settings.is_saas:
        # Single-tenant resolves every request to this slug, so it must match config.
        slug = settings.single_tenant_org_slug

    if await get_org_by_slug(session, slug) is not None:
        raise ConflictError(f"An organization with the slug {slug!r} already exists.")

    org = Organization(
        slug=slug, name=org_name, merchant_level=merchant_level, saq_type=saq_type
    )
    session.add(org)
    await session.flush()

    user = User(
        email=email.strip().lower(),
        full_name=full_name,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    await session.flush()

    session.add(Membership(org_id=org.id, user_id=user.id, role=Role.OWNER))
    await session.flush()

    return org, user

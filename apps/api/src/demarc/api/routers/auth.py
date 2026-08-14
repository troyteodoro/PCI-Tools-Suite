"""Sign-in, sign-out, first-run bootstrap, and the session probe the app shell calls."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select

from demarc.api.deps import AuthDep, SettingsDep, client_ip
from demarc.api.schemas import (
    BootstrapRequest,
    DeploymentStatusResponse,
    LoginRequest,
    OrganizationResponse,
    Permissions,
    SessionResponse,
    UserResponse,
)
from demarc.core.config import Settings
from demarc.core.errors import AuthenticationError
from demarc.core.logging import get_logger
from demarc.db.models.audit import AuditAction
from demarc.db.models.organization import Organization
from demarc.db.models.user import Role, User
from demarc.db.session import auth_session, org_session
from demarc.services import audit as audit_service
from demarc.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        # Lax rather than Strict: the app is a single origin, and Strict would drop the
        # cookie on any inbound link from an email or ticket, which is a common path in.
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )


def _permissions_for(role: Role) -> Permissions:
    return Permissions(
        can_write=not role.is_read_only,
        can_manage_members=role.at_least(Role.OWNER),
        # Auditors need exports; that is the point of handing them a login.
        can_export=role.at_least(Role.AUDITOR),
    )


async def _write_audit(org_id: uuid.UUID, **kwargs: object) -> None:
    """Audit writes are data-plane, so they need their own org-scoped transaction."""
    async with org_session(org_id) as session:
        await audit_service.record(session, org_id=org_id, **kwargs)  # type: ignore[arg-type]


@router.get("/deployment", response_model=DeploymentStatusResponse)
async def deployment_status(settings: SettingsDep) -> DeploymentStatusResponse:
    """Unauthenticated. Tells the frontend whether to show first-run setup or sign-in."""
    async with auth_session() as session:
        bootstrapped = await auth_service.deployment_is_bootstrapped(session)

    return DeploymentStatusResponse(
        bootstrapped=bootstrapped,
        deployment_mode=settings.deployment_mode.value,
        signup_enabled=settings.is_saas,
    )


@router.post("/bootstrap", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
) -> SessionResponse:
    """First-run setup. Closes permanently once any user exists."""
    async with auth_session() as session:
        org, user = await auth_service.bootstrap_deployment(
            session,
            settings=settings,
            org_name=payload.org_name,
            org_slug=payload.org_slug,
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            merchant_level=payload.merchant_level,
            saq_type=payload.saq_type,
        )
        token, _ = await auth_service.create_session(
            session,
            settings=settings,
            user=user,
            org=org,
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        org_id, org_snapshot = org.id, OrganizationResponse.model_validate(org)
        user_snapshot = UserResponse.model_validate(user)

    await _write_audit(
        org_id,
        action=AuditAction.DEPLOYMENT_BOOTSTRAPPED,
        actor_user_id=user_snapshot.id,
        actor_label=user_snapshot.email,
        target_type="organization",
        target_id=str(org_id),
        detail={"org_name": org_snapshot.name, "deployment_mode": settings.deployment_mode.value},
        source_ip=client_ip(request),
    )

    _set_session_cookie(response, settings, token)
    log.info("deployment.bootstrapped", org=org_snapshot.slug, owner=user_snapshot.email)

    return SessionResponse(
        user=user_snapshot,
        organization=org_snapshot,
        role=Role.OWNER,
        permissions=_permissions_for(Role.OWNER),
    )


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    settings: SettingsDep,
) -> SessionResponse:
    source_ip = client_ip(request)

    failed_for: str | None = None
    token: str = ""
    role: Role = Role.VIEWER
    org_snapshot: OrganizationResponse | None = None
    user_snapshot: UserResponse | None = None

    async with auth_session() as session:
        org = await auth_service.resolve_login_org(session, settings, payload.org_slug)
        org_id = org.id
        try:
            user, membership = await auth_service.authenticate(
                session, org=org, email=payload.email, password=payload.password
            )
        except AuthenticationError:
            failed_for = payload.email
        else:
            token, _ = await auth_service.create_session(
                session,
                settings=settings,
                user=user,
                org=org,
                ip_address=source_ip,
                user_agent=request.headers.get("user-agent"),
            )
            org_snapshot = OrganizationResponse.model_validate(org)
            user_snapshot = UserResponse.model_validate(user)
            role = membership.role

    if failed_for is not None or org_snapshot is None or user_snapshot is None:
        # Recorded so repeated failures are visible to whoever reviews the log — which
        # requirement 10.2.1.5 expects for invalid access attempts.
        await _write_audit(
            org_id,
            action=AuditAction.LOGIN_FAILED,
            actor_label=failed_for or payload.email,
            detail={"reason": "invalid_credentials"},
            source_ip=source_ip,
        )
        raise AuthenticationError("Invalid credentials.")

    await _write_audit(
        org_id,
        action=AuditAction.LOGIN_SUCCEEDED,
        actor_user_id=user_snapshot.id,
        actor_label=user_snapshot.email,
        source_ip=source_ip,
    )

    _set_session_cookie(response, settings, token)
    return SessionResponse(
        user=user_snapshot,
        organization=org_snapshot,
        role=role,
        permissions=_permissions_for(role),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, settings: SettingsDep) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    org_id: uuid.UUID | None = None
    actor = "unknown"

    if token:
        async with auth_session() as session:
            context = await auth_service.resolve_session(session, settings=settings, token=token)
            if context is not None:
                actor = context.email
            org_id = await auth_service.revoke_session(session, token=token)

    if org_id is not None:
        await _write_audit(
            org_id,
            action=AuditAction.LOGOUT,
            actor_label=actor,
            source_ip=client_ip(request),
        )

    response.delete_cookie(settings.session_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/session", response_model=SessionResponse)
async def current_session(auth: AuthDep) -> SessionResponse:
    """Called on app load to hydrate the shell."""
    async with auth_session() as session:
        org = (
            await session.execute(select(Organization).where(Organization.id == auth.org_id))
        ).scalar_one()
        user = (await session.execute(select(User).where(User.id == auth.user_id))).scalar_one()

        return SessionResponse(
            user=UserResponse.model_validate(user),
            organization=OrganizationResponse.model_validate(org),
            role=auth.role,
            permissions=_permissions_for(auth.role),
        )

"""Request and response models.

These are the contract the frontend's generated TypeScript client is built from, so
prefer explicit field names over cleverness.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from demarc.db.models.organization import MerchantLevel, SAQType
from demarc.db.models.user import Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- health


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    version: str
    checks: dict[str, str]


# --------------------------------------------------------------------------- auth


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    # Ignored in single-tenant mode, where the org comes from configuration.
    org_slug: str | None = Field(default=None, max_length=63)


class BootstrapRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=255)
    org_slug: str | None = Field(default=None, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*$")
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    # 12 is the floor PCI DSS v4 requirement 8.3.6 sets for the systems it governs.
    # Demarc is not itself in scope by default, but shipping a weaker default would be a
    # poor look for a compliance tool.
    password: str = Field(min_length=12, max_length=1024)
    merchant_level: MerchantLevel = MerchantLevel.UNDECLARED
    saq_type: SAQType = SAQType.D_MERCHANT


class DeploymentStatusResponse(BaseModel):
    """Drives the frontend's first-run screen."""

    bootstrapped: bool
    deployment_mode: str
    signup_enabled: bool


class OrganizationResponse(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    merchant_level: MerchantLevel
    saq_type: SAQType


class UserResponse(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    last_login_at: datetime | None = None


class SessionResponse(BaseModel):
    """Everything the app shell needs on load."""

    user: UserResponse
    organization: OrganizationResponse
    role: Role
    permissions: Permissions


class Permissions(BaseModel):
    can_write: bool
    can_manage_members: bool
    can_export: bool


SessionResponse.model_rebuild()


# --------------------------------------------------------------------------- audit


class AuditEntryResponse(ORMModel):
    id: uuid.UUID
    seq: int
    at: datetime
    actor_label: str
    action: str
    target_type: str | None
    target_id: str | None
    detail: dict[str, object]
    hash: str
    prev_hash: str


class AuditChainStatusResponse(BaseModel):
    ok: bool
    entries_checked: int
    first_bad_seq: int | None = None
    reason: str | None = None
    summary: str

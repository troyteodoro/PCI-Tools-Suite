"""Users and their organization memberships.

A user is a global identity; a membership grants that identity a role in one
organization. In single-tenant deployments a user has exactly one membership. The shape
is identical in SaaS, where a user may hold several.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from demarc.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Role(StrEnum):
    """Ordered least- to most-privileged; see `Role.at_least`.

    `AUDITOR` exists so you can hand a QSA a read-only login without giving them the
    ability to alter evidence — which would defeat the point of the evidence.
    """

    VIEWER = "viewer"
    AUDITOR = "auditor"
    ENGINEER = "engineer"
    OWNER = "owner"

    @property
    def rank(self) -> int:
        return _ROLE_RANK[self]

    def at_least(self, required: Role) -> bool:
        return self.rank >= required.rank

    @property
    def is_read_only(self) -> bool:
        return self in (Role.VIEWER, Role.AUDITOR)


_ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.AUDITOR: 1,
    Role.ENGINEER: 2,
    Role.OWNER: 3,
}


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Membership(Base, UUIDPrimaryKeyMixin, OrgScopedMixin, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_memberships_org_id_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="role", native_enum=False, length=16), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="memberships", lazy="joined")

    def __repr__(self) -> str:
        return f"<Membership user={self.user_id} org={self.org_id} role={self.role}>"

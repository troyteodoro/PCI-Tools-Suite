"""Hash-chained audit log.

This tool's own output is evidence, so its own integrity has to be demonstrable
(docs/spec.md §4, §8). Each entry commits to its predecessor: tampering with entry *n* breaks
every hash from *n* onward, and the chain can be verified offline from an export.

Entries are append-only. There is no update path and no delete path, by design.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from demarc.db.base import Base, OrgScopedMixin, UUIDPrimaryKeyMixin

GENESIS_HASH = "0" * 64


class AuditAction(StrEnum):
    ORG_CREATED = "org.created"
    ORG_UPDATED = "org.updated"
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    MEMBERSHIP_GRANTED = "membership.granted"
    MEMBERSHIP_REVOKED = "membership.revoked"
    MEMBERSHIP_ROLE_CHANGED = "membership.role_changed"
    LOGIN_SUCCEEDED = "auth.login_succeeded"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    SESSION_EXPIRED = "auth.session_expired"
    DEPLOYMENT_BOOTSTRAPPED = "deployment.bootstrapped"


class AuditLogEntry(Base, UUIDPrimaryKeyMixin, OrgScopedMixin):
    __tablename__ = "audit_log"
    __table_args__ = (
        # The chain is per-organization. A gap or duplicate in `seq` is itself evidence
        # of tampering, and the unique constraint makes a concurrent write fail loudly
        # rather than fork the chain.
        UniqueConstraint("org_id", "seq", name="uq_audit_log_org_id_seq"),
    )

    seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    # Denormalized so the entry stays readable after a user is deleted. The chain must
    # not depend on rows that can disappear.
    actor_label: Mapped[str] = mapped_column(String(320), nullable=False)

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)

    source_ip: Mapped[str | None] = mapped_column(String(64))

    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<AuditLogEntry {self.org_id}#{self.seq} {self.action}>"

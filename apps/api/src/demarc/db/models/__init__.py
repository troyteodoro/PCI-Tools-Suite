"""Model registry. Importing this module registers every table on `Base.metadata`,
which is what Alembic autogenerate walks.
"""

from demarc.db.base import Base
from demarc.db.models.audit import GENESIS_HASH, AuditAction, AuditLogEntry
from demarc.db.models.organization import MerchantLevel, Organization, SAQType
from demarc.db.models.session import Session
from demarc.db.models.user import Membership, Role, User

__all__ = [
    "GENESIS_HASH",
    "AuditAction",
    "AuditLogEntry",
    "Base",
    "Membership",
    "MerchantLevel",
    "Organization",
    "Role",
    "SAQType",
    "Session",
    "User",
]

# Tables holding compliance data. RLS is enabled and FORCED on each; the migration keeps
# this list and the database in step. Auth-plane tables are deliberately absent — see
# demarc.db.session for why.
DATA_PLANE_TABLES: tuple[str, ...] = ("audit_log",)

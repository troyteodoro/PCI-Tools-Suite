"""Organizations — the tenant boundary."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from demarc.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MerchantLevel(StrEnum):
    LEVEL_1 = "level_1"
    LEVEL_2 = "level_2"
    LEVEL_3 = "level_3"
    LEVEL_4 = "level_4"
    SERVICE_PROVIDER = "service_provider"
    UNDECLARED = "undeclared"


class SAQType(StrEnum):
    A = "A"
    A_EP = "A-EP"
    B = "B"
    B_IP = "B-IP"
    C = "C"
    C_VT = "C-VT"
    D_MERCHANT = "D-Merchant"
    D_SERVICE_PROVIDER = "D-ServiceProvider"
    P2PE = "P2PE"
    NOT_APPLICABLE = "not_applicable"


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    merchant_level: Mapped[MerchantLevel] = mapped_column(
        SAEnum(MerchantLevel, name="merchant_level", native_enum=False, length=32),
        nullable=False,
        default=MerchantLevel.UNDECLARED,
    )
    # A full SAQ D assessment is the default assumption; narrowed once scope is declared.
    saq_type: Mapped[SAQType] = mapped_column(
        SAEnum(SAQType, name="saq_type", native_enum=False, length=32),
        nullable=False,
        default=SAQType.D_MERCHANT,
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"

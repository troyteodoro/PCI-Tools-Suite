"""Append-only, hash-chained audit log.

Chain rule, fixed for all time — changing it invalidates every existing chain:

    hash_n = SHA256(canonical_json({
        org_id, seq, at (ISO-8601 UTC), actor_user_id, actor_label,
        action, target_type, target_id, detail, source_ip, prev_hash
    }))

`prev_hash` of the first entry in an organization's chain is 64 zeroes (`GENESIS_HASH`).
Verification re-derives every hash from the stored fields and compares, so it works
against an offline export with no database access.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from demarc.core.security import canonical_json, sha256_hex
from demarc.db.models.audit import GENESIS_HASH, AuditAction, AuditLogEntry


def compute_entry_hash(
    *,
    org_id: uuid.UUID,
    seq: int,
    at: datetime,
    actor_user_id: uuid.UUID | None,
    actor_label: str,
    action: str,
    target_type: str | None,
    target_id: str | None,
    detail: dict[str, Any],
    source_ip: str | None,
    prev_hash: str,
) -> str:
    payload = {
        "org_id": str(org_id),
        "seq": seq,
        "at": at.astimezone(UTC).isoformat(),
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "actor_label": actor_label,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "detail": detail,
        "source_ip": source_ip,
        "prev_hash": prev_hash,
    }
    return sha256_hex(canonical_json(payload))


async def record(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    action: AuditAction | str,
    actor_user_id: uuid.UUID | None = None,
    actor_label: str = "system",
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict[str, Any] | None = None,
    source_ip: str | None = None,
) -> AuditLogEntry:
    """Append one entry. Must run inside an `org_session()` transaction.

    Concurrent appends to the same organization would race on `seq` and fork the chain,
    so we take a transaction-scoped advisory lock keyed on the org. It is released at
    commit; contention is per-organization and writes are infrequent.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"audit:{org_id}"},
    )

    tail = (
        await session.execute(
            select(AuditLogEntry.seq, AuditLogEntry.hash)
            .where(AuditLogEntry.org_id == org_id)
            .order_by(AuditLogEntry.seq.desc())
            .limit(1)
        )
    ).first()

    seq = (tail.seq + 1) if tail else 1
    prev_hash = tail.hash if tail else GENESIS_HASH

    at = datetime.now(UTC)
    action_value = action.value if isinstance(action, AuditAction) else action
    detail = detail or {}

    entry = AuditLogEntry(
        org_id=org_id,
        seq=seq,
        at=at,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        action=action_value,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        source_ip=source_ip,
        prev_hash=prev_hash,
        hash=compute_entry_hash(
            org_id=org_id,
            seq=seq,
            at=at,
            actor_user_id=actor_user_id,
            actor_label=actor_label,
            action=action_value,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            source_ip=source_ip,
            prev_hash=prev_hash,
        ),
    )
    session.add(entry)
    await session.flush()
    return entry


@dataclass(frozen=True)
class ChainVerification:
    ok: bool
    entries_checked: int
    first_bad_seq: int | None = None
    reason: str | None = None

    @property
    def summary(self) -> str:
        if self.ok:
            return f"Chain intact across {self.entries_checked} entries."
        return f"Chain broken at seq {self.first_bad_seq}: {self.reason}"


async def verify_chain(session: AsyncSession, *, org_id: uuid.UUID) -> ChainVerification:
    """Re-derive every hash and confirm the links. O(n) — run it in a worker for large logs."""
    entries = (
        (
            await session.execute(
                select(AuditLogEntry)
                .where(AuditLogEntry.org_id == org_id)
                .order_by(AuditLogEntry.seq)
            )
        )
        .scalars()
        .all()
    )

    expected_prev = GENESIS_HASH
    for index, entry in enumerate(entries, start=1):
        if entry.seq != index:
            return ChainVerification(
                ok=False,
                entries_checked=index - 1,
                first_bad_seq=entry.seq,
                reason=f"expected seq {index}, found {entry.seq} (gap or reorder)",
            )
        if entry.prev_hash != expected_prev:
            return ChainVerification(
                ok=False,
                entries_checked=index - 1,
                first_bad_seq=entry.seq,
                reason="prev_hash does not match predecessor",
            )

        recomputed = compute_entry_hash(
            org_id=entry.org_id,
            seq=entry.seq,
            at=entry.at,
            actor_user_id=entry.actor_user_id,
            actor_label=entry.actor_label,
            action=entry.action,
            target_type=entry.target_type,
            target_id=entry.target_id,
            detail=entry.detail,
            source_ip=entry.source_ip,
            prev_hash=entry.prev_hash,
        )
        if recomputed != entry.hash:
            return ChainVerification(
                ok=False,
                entries_checked=index - 1,
                first_bad_seq=entry.seq,
                reason="contents do not match stored hash",
            )

        expected_prev = entry.hash

    return ChainVerification(ok=True, entries_checked=len(entries))


async def count_entries(session: AsyncSession, *, org_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.org_id == org_id)
    )
    return result.scalar_one()

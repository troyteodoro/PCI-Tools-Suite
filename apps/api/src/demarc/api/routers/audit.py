"""Audit log access.

Read-only over HTTP by design: there is no endpoint that edits or deletes an entry,
and the runtime database role holds no UPDATE or DELETE grant on the table either.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from demarc.api.deps import AuthDep, OrgDbDep, require_role
from demarc.api.schemas import AuditChainStatusResponse, AuditEntryResponse
from demarc.db.models.audit import AuditLogEntry
from demarc.db.models.user import Role
from demarc.services import audit as audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "/entries",
    response_model=list[AuditEntryResponse],
    dependencies=[Depends(require_role(Role.AUDITOR))],
)
async def list_entries(
    db: OrgDbDep,
    limit: int = Query(default=100, ge=1, le=500),
    before_seq: int | None = Query(default=None, ge=1),
) -> list[AuditEntryResponse]:
    """Newest first. `before_seq` pages backwards through the chain."""
    query = select(AuditLogEntry).order_by(AuditLogEntry.seq.desc()).limit(limit)
    if before_seq is not None:
        query = query.where(AuditLogEntry.seq < before_seq)

    entries = (await db.execute(query)).scalars().all()
    return [AuditEntryResponse.model_validate(entry) for entry in entries]


@router.get(
    "/chain",
    response_model=AuditChainStatusResponse,
    dependencies=[Depends(require_role(Role.AUDITOR))],
)
async def chain_status(auth: AuthDep, db: OrgDbDep) -> AuditChainStatusResponse:
    """Re-derive every hash and confirm the chain is unbroken.

    O(n) over the organization's entries — fine at M0 volumes, moves to a worker before
    the log gets large.
    """
    result = await audit_service.verify_chain(db, org_id=auth.org_id)
    return AuditChainStatusResponse(
        ok=result.ok,
        entries_checked=result.entries_checked,
        first_bad_seq=result.first_bad_seq,
        reason=result.reason,
        summary=result.summary,
    )

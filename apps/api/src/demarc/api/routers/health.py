"""Liveness and readiness.

`/healthz` answers "is the process up" and must not touch dependencies — a database
blip should not cause an orchestrator to kill a healthy container. `/readyz` answers
"can it serve traffic" and does check them.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import text

from demarc import __version__
from demarc.api.schemas import HealthResponse, ReadinessResponse
from demarc.core.logging import get_logger
from demarc.db.session import auth_session

router = APIRouter(tags=["health"])
log = get_logger(__name__)


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(response: Response) -> ReadinessResponse:
    checks: dict[str, str] = {}

    try:
        async with auth_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - readiness reports, it does not handle
        log.warning("readiness.database_failed", error=str(exc))
        checks["database"] = "unavailable"

    ready = all(value == "ok" for value in checks.values())
    if not ready:
        response.status_code = 503

    return ReadinessResponse(
        status="ready" if ready else "not_ready", version=__version__, checks=checks
    )

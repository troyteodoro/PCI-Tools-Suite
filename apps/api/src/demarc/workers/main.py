"""ARQ worker.

Empty of real jobs at M0 — it exists so the queue, scheduling and container wiring are
proven before M2 puts the payment-page crawl behind them. The crawl runs in a separate
image (Dockerfile.worker.crawl) with no database credentials; see PLAN.md §3.
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings

from demarc.core.config import get_settings
from demarc.core.logging import configure_logging, get_logger

log = get_logger(__name__)


async def heartbeat(ctx: dict[str, Any]) -> str:
    """Proves the scheduler is alive. Replaced by real cron jobs in M2."""
    log.info("worker.heartbeat", job_id=ctx.get("job_id"))
    return "ok"


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)
    ctx["settings"] = settings
    log.info("worker.starting", deployment_mode=settings.deployment_mode.value)


async def shutdown(ctx: dict[str, Any]) -> None:
    from demarc.db.session import dispose_engine

    await dispose_engine()
    log.info("worker.stopped")


class WorkerSettings:
    functions = [heartbeat]
    cron_jobs = [cron(heartbeat, minute={0, 30}, run_at_startup=False)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))
    max_jobs = 10
    job_timeout = 600

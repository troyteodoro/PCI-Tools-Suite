"""FastAPI application factory."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from demarc import __version__
from demarc.api.routers import audit, auth, health
from demarc.core.config import Settings, get_settings
from demarc.core.errors import DemarcError
from demarc.core.logging import configure_logging, get_logger
from demarc.db.session import dispose_engine

log = get_logger(__name__)

API_PREFIX = "/api/v1"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request id to the logging context and echo it back.

    Every log line for a request carries the same id, which is what makes an incident
    reconstructable — and reconstructing incidents is requirement 10's whole point.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(
            request_id=request_id, path=request.url.path, method=request.method
        )
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "path", "method")
        response.headers["x-request-id"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline response headers for the API.

    The frontend is served by nginx/Caddy, which sets the page CSP; these cover the JSON
    surface, where the main risks are sniffing and framing.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log.info(
        "api.starting",
        version=__version__,
        environment=settings.environment.value,
        deployment_mode=settings.deployment_mode.value,
    )
    yield
    await dispose_engine()
    log.info("api.stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Demarc API",
        version=__version__,
        description="PCI DSS evidence and scope tooling.",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # session cookie
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-Id"],
    )

    @app.exception_handler(DemarcError)
    async def handle_demarc_error(request: Request, exc: DemarcError) -> JSONResponse:
        if exc.status_code >= 500:
            log.error("api.error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request body failed validation.",
                    "fields": [
                        {"path": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
                        for err in exc.errors()
                    ],
                }
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(audit.router, prefix=API_PREFIX)

    return app


app = create_app()

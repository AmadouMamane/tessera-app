"""FastAPI application factory and uvicorn entry point.

The factory wires every cross-cutting concern in a single place:

* OTel tracing, Prometheus metrics, structlog logging.
* Bearer-token auth middleware (configured per environment).
* Request-ID propagation for cross-service correlation.
* CORS for the bundled dashboard.
* All routers (chat, audit, health).

The :func:`cli` entry point is exposed as the ``tessera`` console script in
``pyproject.toml`` — it boots uvicorn against the factory.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from tessera import __version__
from tessera.api.limits import RequestSizeLimitMiddleware
from tessera.api.middleware import AuthMiddleware, RequestIdMiddleware
from tessera.api.ratelimit import RateLimitMiddleware
from tessera.api.routes import (
    audit,
    chat,
    health,
    memory,
    observability,
    settings as settings_routes,
    sources,
)
from tessera.api.security import SecurityHeadersMiddleware, require_bearer
from tessera.memory.governance import ensure_consent_schema
from tessera.memory.persistent import ensure_longterm_schema
from tessera.memory.summary import ensure_summary_schema
from tessera.memory.transcript import ensure_transcript_schema
from tessera.observability import logging as obs_logging, metrics, traces
from tessera.retrieval.store import get_pool
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

__all__ = ["build_app", "cli"]


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Open + close the resources that outlive a single request."""
    obs_logging.configure()
    traces.configure()
    metrics.configure()
    pool = get_pool()
    try:
        await pool.open()
        await ensure_transcript_schema()  # ADR 0007, Mechanism A
        await ensure_summary_schema()  # ADR 0007, Tier 1
        await ensure_longterm_schema()  # ADR 0007, Tier 2
        await ensure_consent_schema()  # ADR 0007, governance
        yield
    finally:
        await pool.close()


def build_app() -> FastAPI:
    """Construct the FastAPI application."""
    settings = get_settings()
    # Docs/OpenAPI are on for local dev, off in production, and can be closed
    # explicitly (expose_docs=False) on an internet-reachable non-prod agent.
    docs_on = settings.api.expose_docs and not settings.is_production()
    app = FastAPI(
        title="Tessera",
        version=__version__,
        description=(
            "Multilingual (FR/DE/EN) banking support LLM agent, grounded in EU "
            "regulatory corpora and guarded by mcp-firewall."
        ),
        docs_url="/docs" if docs_on else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_on else None,
        lifespan=_lifespan,
    )

    if settings.api.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["authorization", "content-type", "x-request-id"],
            allow_credentials=False,
        )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(AuthMiddleware)
    # Added last → outermost, so security headers cover every response,
    # including the 401s / 429s produced by inner middleware (ADR 0008).
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(health.router)
    app.include_router(chat.router)
    # Defence in depth: the read surfaces require the bearer token at the route
    # level too, not only via the global middleware (ADR 0008).
    app.include_router(audit.router, dependencies=[Depends(require_bearer)])
    app.include_router(memory.router, dependencies=[Depends(require_bearer)])
    app.include_router(observability.router, dependencies=[Depends(require_bearer)])
    app.include_router(settings_routes.router, dependencies=[Depends(require_bearer)])
    app.include_router(sources.router, dependencies=[Depends(require_bearer)])

    FastAPIInstrumentor.instrument_app(app)
    return app


def cli() -> None:
    """Console-script entry point — boots the API via uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "tessera.api.main:build_app",
        host=settings.api.host,
        port=settings.api.port,
        factory=True,
        log_level=settings.observability.log_level.lower(),
        access_log=False,  # delegated to structlog via middleware
    )

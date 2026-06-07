"""Cross-cutting HTTP middlewares: request-ID and bearer-token auth."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from tessera.observability.context import reset_request_context, set_request_context
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.types import ASGIApp

__all__ = ["AuthMiddleware", "RequestIdMiddleware"]


_REQUEST_ID_HEADER = "x-request-id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request-ID to every request and propagate it to logs and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Inject a request-ID header and bind it to the structlog context."""
        existing = request.headers.get(_REQUEST_ID_HEADER)
        request_id = existing or secrets.token_hex(8)
        structlog.contextvars.bind_contextvars(request_id=request_id)
        token = set_request_context(request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
            reset_request_context(token)
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional bearer-token guard.

    The check is skipped entirely when ``api.bearer_token`` is unset so the
    health and metrics paths remain reachable in CI without secret material.
    """

    _EXEMPT_PATHS: frozenset[str] = frozenset(
        {"/healthz", "/readyz", "/metrics", "/docs", "/openapi.json"}
    )

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        token = get_settings().api.bearer_token
        self._expected = token.get_secret_value() if token is not None else None

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Enforce bearer-token authentication, exempting health and metrics paths."""
        if self._expected is None or request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            return JSONResponse({"detail": "missing bearer token"}, status_code=401)
        presented = header[len("bearer ") :].strip()
        if not secrets.compare_digest(presented, self._expected):
            return JSONResponse({"detail": "invalid bearer token"}, status_code=401)
        return await call_next(request)

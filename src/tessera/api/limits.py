"""Request-body size ceiling middleware (ADR 0020).

Per-field Pydantic caps bound individual fields, but nothing bounds the
*aggregate* request body — 40 history messages x 8 000 chars is ~320 kB before
the model even runs. This middleware rejects oversized bodies early with 413,
independently of rate limiting, as a cost/DoS amplifier guard.

It checks the ``Content-Length`` header when present (cheap, the common case)
and otherwise streams-and-counts up to the ceiling so a chunked/omitted-length
body cannot bypass the check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response

__all__ = ["RequestSizeLimitMiddleware"]

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE"})


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies larger than ``api.max_request_bytes`` with 413."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Enforce the body ceiling before the route handler runs."""
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        ceiling = get_settings().api.max_request_bytes

        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > ceiling:
                    return _too_large(ceiling)
            except ValueError:
                return JSONResponse({"detail": "invalid content-length"}, status_code=400)

        # No / untrusted Content-Length: count the body, capping at the ceiling.
        body = await request.body()
        if len(body) > ceiling:
            return _too_large(ceiling)
        return await call_next(request)


def _too_large(ceiling: int) -> JSONResponse:
    return JSONResponse(
        {"detail": f"request body exceeds {ceiling} bytes"},
        status_code=413,
    )

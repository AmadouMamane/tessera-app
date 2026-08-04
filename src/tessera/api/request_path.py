"""The path a security decision may be taken on — the one the router will dispatch.

``request.url.path`` looks like the request's path and is not it. Starlette builds
``request.url`` by concatenating ``{scheme}://{Host header}{path}`` and **re-parsing the
result**, so a value an attacker controls (the ``Host`` header) decides how the path is parsed.
Routing does no such thing: it dispatches on ``scope["path"]``, the raw value the ASGI server
put there.

Two different answers to "what path is this?", and every middleware in this codebase asked the
wrong one. The gap is exploitable, not theoretical. With

    Host: example.com/healthz#

the reconstructed URL is ``http://example.com/healthz#/chat``; ``urlsplit`` reads the fragment
off, and ``request.url.path`` becomes exactly ``/healthz`` — a member of
``AuthMiddleware._EXEMPT_PATHS``. The bearer check waves the request through, and the router,
reading ``scope["path"]``, dispatches it to ``/chat``. Unauthenticated, from the network.

Starlette fixed the reconstruction in 1.0.1 (PYSEC-2026-161, and PYSEC-2026-248 for the related
path-validation gap), and this repository now pins ``>=1.3.1``. This module is the other half,
and the half that does not expire: the check and the dispatch read the *same* value, so they
cannot disagree — whatever a future version of the framework decides ``request.url`` means.

ADR 0026, in its usual shape: interrogate the thing (the path that will be routed), never its
neighbourhood (a URL rebuilt from a header).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["routed_path"]


def routed_path(request: Request) -> str:
    """Return the path the router will dispatch on.

    Args:
        request: The inbound request.

    Returns:
        ``scope["path"]`` — the raw ASGI path, never reconstructed from a header. Falls back to
        ``request.url.path`` only if the scope carries no path at all, which no ASGI server
        does; the fallback exists so a hand-built scope in a test cannot raise here.
    """
    path = request.scope.get("path")
    return path if isinstance(path, str) else request.url.path

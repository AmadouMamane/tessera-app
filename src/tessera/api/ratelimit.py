"""Rate limiting middleware (ADR 0008).

The windowing and storage are delegated to the ``limits`` library (the same
engine that backs slowapi) — we do not reinvent the algorithm. Tessera adds only
a thin, deployment-aware middleware:

* a **key function** that prefers the bearer-token identity over the client IP,
  so an authenticated caller is limited as themselves, not by shared NAT;
* **per-surface limits**: a strict limit on ``POST /chat`` (LLM cost) and a
  looser one on the read endpoints;
* **deployment-aware enforcement**: on-prem there is no upstream load balancer to
  absorb abuse, so the limiter cannot be silently disabled there
  (``Settings.rate_limit_required``).

Storage defaults to in-memory (per-instance). For multi-instance Cloud Run, set
``api.rate_limit_storage_uri`` to a shared ``redis://`` URI for global limits.
"""

from __future__ import annotations

import contextlib
import threading
from typing import TYPE_CHECKING

from limits import RateLimitItem, parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterator

    from starlette.requests import Request
    from starlette.responses import Response

__all__ = [
    "InvokeLimiter",
    "InvokeThrottledError",
    "RateLimitMiddleware",
    "client_identity",
    "get_invoke_limiter",
    "reset_invoke_limiter",
]

# Endpoints that get the strict (LLM-cost) limit; everything else gets the read
# limit. Keyed by (method, path).
_STRICT_ROUTES: frozenset[tuple[str, str]] = frozenset({("POST", "/chat")})
# Never rate-limit liveness/readiness/metrics — they must stay scrapeable.
_EXEMPT_PATHS: frozenset[str] = frozenset({"/healthz", "/readyz", "/metrics"})


def client_identity(request: Request) -> str:
    """Rate-limit key for the calling client.

    Priority:

    1. ``X-Session-Id`` — the per-browser session the front forwards (set as an
       httpOnly cookie). This is the real per-client signal: the bearer token is
       a *shared* front→backend secret, so keying on it would collapse every
       caller into a single bucket.
    2. The forwarded client IP (first hop of ``X-Forwarded-For`` /
       ``CF-Connecting-IP``) — only when ``trust_forwarded_headers`` is set, i.e.
       behind a proxy that populates them.
    3. The immediate peer address.
    """
    session = request.headers.get("x-session-id", "").strip()
    if session:
        return f"sess:{session}"
    if get_settings().api.trust_forwarded_headers:
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get(
            "cf-connecting-ip", ""
        )
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return f"ip:{first_hop}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


# Constant key for the global (all-sessions) ceiling on the LLM endpoint.
_GLOBAL_CHAT_KEY = "global:chat"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiting backed by the ``limits`` library."""

    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        settings = get_settings()
        self._enabled = settings.rate_limit_required
        self._strict: RateLimitItem = parse(settings.api.rate_limit_chat)
        self._global: RateLimitItem = parse(settings.api.rate_limit_chat_global)
        self._read: RateLimitItem = parse(settings.api.rate_limit_read)
        storage_uri = settings.api.rate_limit_storage_uri or "memory://"
        self._limiter = MovingWindowRateLimiter(storage_from_string(storage_uri))

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Check the limit for this caller+surface, else 429."""
        if not self._enabled or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        identity = client_identity(request)
        # The LLM endpoint gets two buckets that must BOTH pass: the per-session
        # limit and a hard global ceiling on total cost. Everything else gets the
        # looser read limit. (method, path) keys the strict set.
        if (request.method, request.url.path) in _STRICT_ROUTES:
            checks: list[tuple[RateLimitItem, str]] = [
                (self._strict, identity),
                (self._global, _GLOBAL_CHAT_KEY),
            ]
        else:
            checks = [(self._read, identity)]

        # Test all buckets without consuming, so a rejection by one does not burn
        # a token in the others; only commit (hit) once every bucket has room.
        for item, key in checks:
            if not self._limiter.test(item, key, request.url.path):
                return JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": str(item.get_expiry())},
                )
        for item, key in checks:
            self._limiter.hit(item, key, request.url.path)
        return await call_next(request)


# ── Invocation-seam limiter (ADR 0019 open question) ────────────────────────────
# POST /agents/{id}/invoke was bounded only by the generic read limit. This adds a
# purpose-built limit keyed PER AGENT (binding) and PER ROLE (the operator surface),
# plus a concurrency cap — "an operator hammering a production agent's test endpoint is a
# governance question, not just an infra one" (ADR 0019 §Open questions). The rate window
# reuses the same `limits` engine and storage as the middleware; the concurrency cap is a
# small in-process in-flight counter.


class InvokeThrottledError(Exception):
    """The invocation seam refused a turn (rate or concurrency). Carries a Retry-After (s)."""

    def __init__(self, retry_after: int, reason: str) -> None:
        super().__init__(reason)
        self.retry_after = retry_after
        self.reason = reason


class InvokeLimiter:
    """Per-(agent, role) rate limit + concurrency cap for the declared invocation seam.

    The rate is a moving window (the `limits` engine, so a shared ``redis://`` store gives
    cross-instance limits); the concurrency cap counts in-flight turns per (agent, role) in
    this process. Both refuse with an honest 429 + Retry-After, never a silent drop.
    """

    def __init__(self, *, rate: str, max_concurrent: int, storage_uri: str, enabled: bool) -> None:
        self._enabled = enabled
        self._rate: RateLimitItem = parse(rate)
        self._max_concurrent = max_concurrent
        self._limiter = MovingWindowRateLimiter(storage_from_string(storage_uri))
        self._inflight: dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _rate_key(agent_id: str, role: str, subject: str) -> str:
        return f"invoke:{agent_id}:{role}:{subject}"

    @staticmethod
    def _conc_key(agent_id: str, role: str) -> str:
        return f"invoke:{agent_id}:{role}"

    def check_rate(self, *, agent_id: str, role: str, subject: str) -> None:
        """Consume one rate token; raise :class:`InvokeThrottledError` when the window is spent."""
        if not self._enabled:
            return
        if not self._limiter.hit(self._rate, self._rate_key(agent_id, role, subject)):
            raise InvokeThrottledError(self._rate.get_expiry(), "invocation rate limit exceeded")

    @contextlib.contextmanager
    def concurrency_slot(self, *, agent_id: str, role: str) -> Iterator[None]:
        """Hold one in-flight slot for this (agent, role); raise when it is already at capacity."""
        if not self._enabled:
            yield
            return
        key = self._conc_key(agent_id, role)
        with self._lock:
            if self._inflight.get(key, 0) >= self._max_concurrent:
                raise InvokeThrottledError(1, "invocation concurrency limit reached")
            self._inflight[key] = self._inflight.get(key, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                remaining = self._inflight.get(key, 0) - 1
                if remaining <= 0:
                    self._inflight.pop(key, None)
                else:
                    self._inflight[key] = remaining


_invoke_limiter: InvokeLimiter | None = None


def get_invoke_limiter() -> InvokeLimiter:
    """The process singleton, built from settings on first use (rate window + concurrency cap)."""
    global _invoke_limiter
    if _invoke_limiter is None:
        settings = get_settings()
        _invoke_limiter = InvokeLimiter(
            rate=settings.api.rate_limit_invoke,
            max_concurrent=settings.api.invoke_max_concurrent,
            storage_uri=settings.api.rate_limit_storage_uri or "memory://",
            enabled=settings.rate_limit_required,
        )
    return _invoke_limiter


def reset_invoke_limiter() -> None:
    """Test seam: drop the singleton so the next call rebuilds from current settings."""
    global _invoke_limiter
    _invoke_limiter = None

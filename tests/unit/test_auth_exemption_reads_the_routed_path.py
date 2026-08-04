"""A path-based security decision reads the path the ROUTER will use, never a rebuilt URL.

``AuthMiddleware`` exempts ``/healthz``, ``/readyz``, ``/metrics``, ``/docs`` and
``/openapi.json`` from the bearer check, and the rate limiter exempts and classifies on the
same kind of comparison. Both used to ask ``request.url.path``, which Starlette builds by
concatenating ``{scheme}://{Host header}{path}`` and re-parsing it — so an attacker-controlled
header decided how the path parsed, while the router dispatched on ``scope["path"]``.

The concrete bypass, with ``Host: example.com/healthz#``: the reconstructed URL is
``http://example.com/healthz#/chat``, the fragment is split off, ``request.url.path`` is exactly
``/healthz``, the bearer check waves it through — and the router sends it to ``/chat``.

It was live, not theoretical. Measured against the exact version that was locked, deployed and
serving on 2026-08-04, with this codebase's own exempt set::

    starlette 0.52.1
    Host: example.com/healthz#   scope["path"]=/chat   request.url.path=/healthz   exempt=True
    Host: example.com/metrics#   scope["path"]=/chat   request.url.path=/metrics   exempt=True

**Be exact about what these tests prove.** Starlette closed the reconstruction in 1.0.1
(PYSEC-2026-161 / -248) and this repo now pins ``>=1.3.1``; under that version no divergence
between the two paths is producible at all, so these tests would pass even with the old
``request.url.path`` code. They are not the proof that ``routed_path`` fixes anything today —
the version bump is. They pin the *property* (an attacker-supplied header never decides an
exemption) and the *contract* (the check reads what the router reads), so the day some future
version reintroduces a gap between those two answers, this codebase does not reopen with it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from tessera.api.middleware import AuthMiddleware
from tessera.api.request_path import routed_path

if TYPE_CHECKING:
    import pytest
    from starlette.requests import Request

_TOKEN = "s3cret-operator-token"  # noqa: S105 — a test fixture, not a credential

#: The header value that turned an exempt-path comparison into an auth bypass.
_POISONED_HOST = "example.com/healthz#"


def _app(monkeypatch: pytest.MonkeyPatch) -> Starlette:
    """A minimal app with the real ``AuthMiddleware`` and one protected route."""
    from tessera.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        type(settings.api),
        "bearer_token",
        property(lambda _self: _Secret(_TOKEN)),
        raising=False,
    )

    async def chat(_request: Request) -> JSONResponse:
        return JSONResponse({"reached": "chat"})

    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"reached": "healthz"})

    app = Starlette(routes=[Route("/chat", chat, methods=["POST"]), Route("/healthz", healthz)])
    app.add_middleware(AuthMiddleware)
    return app


class _Secret:
    """The tiny surface of ``SecretStr`` that ``AuthMiddleware.__init__`` uses."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


class TestThePoisonedHostDoesNotExemptAProtectedRoute:
    def test_a_protected_route_is_still_401_under_the_poisoned_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = TestClient(_app(monkeypatch), base_url="http://example.com")
        response = client.post("/chat", headers={"Host": _POISONED_HOST})
        assert response.status_code == 401, (
            "the Host header decided the exemption — an unauthenticated request reached a "
            f"protected route (body: {response.text[:200]})"
        )

    def test_the_same_route_passes_with_the_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Anti-vacuity: prove the 401 above is the middleware refusing, not the route missing."""
        client = TestClient(_app(monkeypatch), base_url="http://example.com")
        response = client.post("/chat", headers={"Authorization": f"Bearer {_TOKEN}"})
        assert response.status_code == 200
        assert response.json() == {"reached": "chat"}

    def test_a_genuinely_exempt_path_is_still_exempt(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Anti-vacuity, the other way: the fix must not close the intended exemption."""
        client = TestClient(_app(monkeypatch), base_url="http://example.com")
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"reached": "healthz"}


class TestRoutedPathIsTheScopePath:
    """The contract, asserted on the scope directly — no HTTP layer to hide behind."""

    def test_it_returns_the_scope_path_verbatim(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "raw_path": b"/chat",
            "root_path": "",
            "query_string": b"",
            "scheme": "http",
            "headers": [(b"host", _POISONED_HOST.encode())],
            "server": ("example.com", 80),
            "client": ("1.2.3.4", 5),
            "http_version": "1.1",
        }
        from starlette.requests import Request as _Request

        assert routed_path(_Request(scope)) == "/chat"

    def test_it_follows_the_scope_when_the_two_answers_differ(self) -> None:
        """The whole point, forced: when they disagree, the ROUTER's answer wins.

        Under the pinned starlette they never disagree, so the divergence is constructed here
        rather than hoped for. Without this, every assertion in this file would still pass if
        ``routed_path`` simply returned ``request.url.path``.
        """

        class _Divergent:
            scope: ClassVar[dict[str, object]] = {"path": "/chat"}

            class url:  # noqa: N801 — a stand-in for starlette's URL attribute
                path = "/healthz"

        assert routed_path(_Divergent()) == "/chat"  # type: ignore[arg-type]

    def test_it_falls_back_only_when_the_scope_carries_no_path(self) -> None:
        class _NoPath:
            scope: ClassVar[dict[str, object]] = {}

            class url:  # noqa: N801
                path = "/healthz"

        assert routed_path(_NoPath()) == "/healthz"  # type: ignore[arg-type]

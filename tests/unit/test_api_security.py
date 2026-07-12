"""Unit tests for the ADR 0020 security hardening layer.

Covered: security headers (presence + HSTS gating on TLS termination),
route-level authz on the read surfaces, request-size ceiling (413), the
deployment-mode helpers, and the deployment-aware secret provider selection.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tessera.settings import DeploymentMode, get_settings


@pytest.fixture
def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A TestClient with no bearer token configured (CI posture)."""
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    get_settings.cache_clear()
    from tessera.api.main import build_app

    return TestClient(build_app())


class TestSecurityHeaders:
    def test_headers_present_on_health(self, _client: TestClient) -> None:
        r = _client.get("/healthz")
        assert r.status_code == 200
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in r.headers
        assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_hsts_present_when_tls_terminated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_API__TLS_TERMINATED", "true")
        get_settings.cache_clear()
        from tessera.api.main import build_app

        client = TestClient(build_app())
        r = client.get("/healthz")
        assert "strict-transport-security" in r.headers

    def test_hsts_absent_when_tls_not_terminated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_API__TLS_TERMINATED", "false")
        get_settings.cache_clear()
        from tessera.api.main import build_app

        client = TestClient(build_app())
        r = client.get("/healthz")
        assert "strict-transport-security" not in r.headers


class TestRouteAuthz:
    def test_audit_requires_bearer_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_API__BEARER_TOKEN", "s3cret-token")
        get_settings.cache_clear()
        from tessera.api.main import build_app

        client = TestClient(build_app())
        # Missing token → 401.
        assert client.get("/audit").status_code == 401
        # Wrong token → 401.
        bad = client.get("/audit", headers={"authorization": "Bearer nope"})
        assert bad.status_code == 401
        # Correct token → not 401 (200 with an empty/absent log is fine).
        ok = client.get("/audit", headers={"authorization": "Bearer s3cret-token"})
        assert ok.status_code != 401

    def test_audit_open_when_no_token(self, _client: TestClient) -> None:
        # No token configured (CI/local posture) → reachable, mirroring AuthMiddleware.
        assert _client.get("/audit").status_code != 401


class TestRequestSizeLimit:
    def test_oversized_body_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_API__MAX_REQUEST_BYTES", "1000")
        monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
        get_settings.cache_clear()
        from tessera.api.main import build_app

        client = TestClient(build_app())
        big = {"message": "x" * 5000}
        r = client.post("/chat", json=big)
        assert r.status_code == 413


class TestDeploymentMode:
    def test_on_prem_forces_rate_limit_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_DEPLOYMENT_MODE", "on_prem")
        monkeypatch.setenv("TESSERA_API__RATE_LIMIT_ENABLED", "false")
        get_settings.cache_clear()
        s = get_settings()
        assert s.deployment_mode is DeploymentMode.ON_PREM
        assert s.is_on_prem() is True
        # On-prem cannot silently disable the limiter.
        assert s.rate_limit_required is True

    def test_cloud_run_respects_disable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_DEPLOYMENT_MODE", "cloud_run")
        monkeypatch.setenv("TESSERA_API__RATE_LIMIT_ENABLED", "false")
        get_settings.cache_clear()
        s = get_settings()
        assert s.rate_limit_required is False


def _ratelimited_client(monkeypatch: pytest.MonkeyPatch, **env: str) -> TestClient:
    """A TestClient over a minimal app carrying only RateLimitMiddleware.

    Avoids build_app() so the dummy /chat route never touches the agent/DB —
    the middleware is the unit under test.
    """
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from fastapi import FastAPI

    from tessera.api.ratelimit import RateLimitMiddleware

    app = FastAPI()

    @app.post("/chat")
    def _chat() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/audit")
    def _audit() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)
    return TestClient(app)


class TestChatRateLimit:
    def test_per_session_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _ratelimited_client(
            monkeypatch,
            TESSERA_API__RATE_LIMIT_CHAT="2/hour",
            TESSERA_API__RATE_LIMIT_CHAT_GLOBAL="100/hour",
        )
        hdr = {"X-Session-Id": "sess-A"}
        assert client.post("/chat", headers=hdr).status_code == 200
        assert client.post("/chat", headers=hdr).status_code == 200
        # Third call for the same session is throttled.
        assert client.post("/chat", headers=hdr).status_code == 429
        # A different session has its own bucket.
        assert client.post("/chat", headers={"X-Session-Id": "sess-B"}).status_code == 200

    def test_global_cap_across_sessions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _ratelimited_client(
            monkeypatch,
            TESSERA_API__RATE_LIMIT_CHAT="100/hour",
            TESSERA_API__RATE_LIMIT_CHAT_GLOBAL="2/hour",
        )
        # Each session is under its own limit, but the global ceiling is 2.
        assert client.post("/chat", headers={"X-Session-Id": "s1"}).status_code == 200
        assert client.post("/chat", headers={"X-Session-Id": "s2"}).status_code == 200
        assert client.post("/chat", headers={"X-Session-Id": "s3"}).status_code == 429

    def test_read_endpoint_uses_loose_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _ratelimited_client(
            monkeypatch,
            TESSERA_API__RATE_LIMIT_CHAT="1/hour",
            TESSERA_API__RATE_LIMIT_READ="100/minute",
        )
        # The strict /chat limit must not apply to the read surface.
        for _ in range(5):
            assert client.get("/audit").status_code == 200


class TestRateLimitIdentity:
    def test_forwarded_ip_isolated_when_trusted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _ratelimited_client(
            monkeypatch,
            TESSERA_API__TRUST_FORWARDED_HEADERS="true",
            TESSERA_API__RATE_LIMIT_CHAT="1/hour",
            TESSERA_API__RATE_LIMIT_CHAT_GLOBAL="100/hour",
        )
        # No session header → key falls to the forwarded IP. Distinct IPs are
        # independent buckets.
        assert client.post("/chat", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.post("/chat", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
        # Same IP again → throttled.
        assert client.post("/chat", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429

    def test_forwarded_ip_ignored_when_untrusted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _ratelimited_client(
            monkeypatch,
            TESSERA_API__TRUST_FORWARDED_HEADERS="false",
            TESSERA_API__RATE_LIMIT_CHAT="1/hour",
            TESSERA_API__RATE_LIMIT_CHAT_GLOBAL="100/hour",
        )
        # Forwarded headers are not trusted → both requests collapse onto the
        # same peer identity, so the second is throttled despite a different XFF.
        assert client.post("/chat", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.post("/chat", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429


class TestChatAuth:
    def test_chat_requires_bearer_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TESSERA_API__BEARER_TOKEN", "s3cret-token")
        get_settings.cache_clear()
        from tessera.api.main import build_app

        client = TestClient(build_app())
        # AuthMiddleware rejects before the agent route runs → no DB needed.
        assert client.post("/chat", json={"message": "hi"}).status_code == 401


class TestSecretProvider:
    def test_default_is_env_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tessera.secrets import EnvSecretProvider, get_secret_provider

        monkeypatch.setenv("TESSERA_SECRETS__PROVIDER", "env")
        monkeypatch.setenv("FOO_SECRET", "bar")
        get_settings.cache_clear()
        get_secret_provider.cache_clear()
        provider = get_secret_provider()
        assert isinstance(provider, EnvSecretProvider)
        assert provider.get("FOO_SECRET") == "bar"
        assert provider.get("MISSING") is None

    def test_resolve_secret_reads_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tessera.secrets import get_secret_provider, resolve_secret

        monkeypatch.setenv("TESSERA_SECRETS__PROVIDER", "env")
        monkeypatch.setenv("TESSERA_TEST_SECRET", "value-123")
        get_settings.cache_clear()
        get_secret_provider.cache_clear()
        assert resolve_secret("TESSERA_TEST_SECRET") == "value-123"

    def test_misconfigured_vault_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from tessera.secrets import EnvSecretProvider, get_secret_provider

        # provider=vault but no url/token → must not crash; degrade to env.
        monkeypatch.setenv("TESSERA_SECRETS__PROVIDER", "vault")
        monkeypatch.delenv("TESSERA_SECRETS__VAULT_URL", raising=False)
        get_settings.cache_clear()
        get_secret_provider.cache_clear()
        assert isinstance(get_secret_provider(), EnvSecretProvider)


class TestReadiness:
    """`/readyz` must reflect LLM reachability, not just process liveness, so a
    container is only healthy when it can actually answer (not silently escalate)."""

    def _client(self, monkeypatch: pytest.MonkeyPatch, *, reachable: bool) -> TestClient:
        from tessera.api.routes import health

        async def _stub() -> bool:
            return reachable

        monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
        monkeypatch.setattr(health, "_llm_reachable", _stub)
        get_settings.cache_clear()
        from tessera.api.main import build_app

        return TestClient(build_app())

    def test_readyz_ready_when_llm_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = self._client(monkeypatch, reachable=True).get("/readyz")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"

    def test_readyz_503_when_llm_unreachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        r = self._client(monkeypatch, reachable=False).get("/readyz")
        assert r.status_code == 503
        assert r.json()["status"] == "llm_unreachable"

    def test_healthz_stays_up_regardless_of_llm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Liveness must not depend on the LLM — only readiness does.
        r = self._client(monkeypatch, reachable=False).get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestDocsExposure:
    """/docs and /openapi.json must be closable on an internet-reachable agent."""

    def _app(self, monkeypatch: pytest.MonkeyPatch, *, expose: bool) -> TestClient:
        monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
        monkeypatch.setenv("TESSERA_API__EXPOSE_DOCS", "true" if expose else "false")
        get_settings.cache_clear()
        from tessera.api.main import build_app

        return TestClient(build_app())

    def test_openapi_open_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._app(monkeypatch, expose=True).get("/openapi.json").status_code == 200

    def test_openapi_closed_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._app(monkeypatch, expose=False).get("/openapi.json").status_code == 404
        assert self._app(monkeypatch, expose=False).get("/docs").status_code == 404

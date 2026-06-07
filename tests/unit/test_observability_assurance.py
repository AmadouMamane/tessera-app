"""Unit tests for the observability assurance V1 primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi.testclient import TestClient

from tessera.observability.evidence import build_turn_evidence_bundle
from tessera.observability.privacy import hash_identifier, sanitize_attributes
from tessera.observability.profiles import resolve_profile
from tessera.settings import AssuranceLevel, ObservabilityProfile, get_settings

if TYPE_CHECKING:
    import pytest


def test_profile_defaults_to_local_dev_in_local_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local development stays lightweight unless explicitly configured."""
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "local")
    get_settings.cache_clear()
    profile = resolve_profile()
    assert profile.name is ObservabilityProfile.LOCAL_DEV
    assert profile.assurance_level is AssuranceLevel.L1_CORRELATED
    assert profile.collector_required is False


def test_cloud_regulated_profile_requires_collector_and_signing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regulated cloud posture opts into stronger evidence expectations."""
    monkeypatch.setenv("TESSERA_ENVIRONMENT", "production")
    monkeypatch.setenv("TESSERA_DEPLOYMENT_MODE", "cloud_run")
    get_settings.cache_clear()

    profile = resolve_profile()

    assert profile.name is ObservabilityProfile.CLOUD_GCP_REGULATED
    assert profile.assurance_level is AssuranceLevel.L4_REPLAYABLE
    assert profile.collector_required is True
    assert profile.evidence_signing_enabled is True


def test_privacy_gateway_drops_forbidden_and_unknown_attributes() -> None:
    """Only contract-approved attributes survive telemetry export."""
    sanitized = sanitize_attributes(
        {
            "language": "fr",
            "raw_prompt": "please leak this",
            "unknown": "value",
            "trace_id": "trace-1",
        }
    )
    assert sanitized == {"language": "fr", "trace_id": "trace-1"}


def test_privacy_gateway_redacts_pii_values() -> None:
    """Allowed fields are still redacted when the value contains PII."""
    sanitized = sanitize_attributes({"model": "customer FR7612345987650123456789014"})
    assert sanitized["model"] == "[REDACTED:iban]"


def test_hash_identifier_is_stable_and_non_plaintext() -> None:
    """Correlation hashes must be stable but not reveal the input."""
    first = hash_identifier("conversation-123")
    second = hash_identifier("conversation-123")
    assert first == second
    assert first.startswith("sha256:")
    assert "conversation-123" not in first


def test_evidence_bundle_is_redacted_and_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Evidence bundles carry profile metadata and never keep raw PII fields."""
    monkeypatch.setenv("TESSERA_OBS_PROFILE", "demo_premium")
    get_settings.cache_clear()

    bundle = build_turn_evidence_bundle(
        conversation_id=UUID(int=1),
        turn_id=UUID(int=2),
        trace_id="trace-abc",
        model="gpt-test",
        language="fr",
        attributes={
            "language": "fr",
            "raw_prompt": "forbidden",
            "model": "FR7612345987650123456789014",
        },
    )
    body = bundle.model_dump()

    assert body["profile"] == "demo_premium"
    assert body["assurance_level"] == "L3"
    assert body["signature"] is not None
    assert body["attributes"] == {"language": "fr", "model": "[REDACTED:iban]"}


def test_observability_status_endpoint_reports_degraded_when_required_collector_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The operator endpoint exposes profile gaps without probing the network."""
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    monkeypatch.setenv("TESSERA_OBS_PROFILE", "cloud_gcp_regulated")
    monkeypatch.delenv("TESSERA_OBS_OTEL_ENDPOINT", raising=False)
    monkeypatch.delenv("TESSERA_OBS_CLOUD_LOGGING_PROJECT", raising=False)
    get_settings.cache_clear()
    from tessera.api.main import build_app

    client = TestClient(build_app())
    response = client.get("/observability/status")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "cloud_gcp_regulated"
    assert body["status"] == "degraded"
    assert "collector_required_but_not_configured" in body["warnings"]


def test_observability_evidence_preview_endpoint_redacts_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API can preview a redacted evidence bundle for dashboard workflows."""
    monkeypatch.delenv("TESSERA_API__BEARER_TOKEN", raising=False)
    monkeypatch.setenv("TESSERA_OBS_PROFILE", "demo_premium")
    get_settings.cache_clear()
    from tessera.api.main import build_app

    client = TestClient(build_app())
    response = client.post(
        "/observability/evidence/preview",
        json={
            "conversation_id": "00000000-0000-0000-0000-000000000001",
            "turn_id": "00000000-0000-0000-0000-000000000002",
            "trace_id": "trace-abc",
            "model": "gpt-test",
            "language": "fr",
            "attributes": {
                "language": "fr",
                "raw_prompt": "do not export",
                "model": "user@example.com",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "demo_premium"
    assert body["signature"] is not None
    assert body["attributes"] == {"language": "fr", "model": "[REDACTED:email]"}

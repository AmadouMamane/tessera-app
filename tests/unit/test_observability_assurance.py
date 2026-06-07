"""Unit tests for the observability assurance V1 primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi.testclient import TestClient

from tessera.observability.actions import (
    active_policy_hash,
    issue_decision_proof,
    validate_decision_proof,
)
from tessera.observability.digital_twin import run_assurance_twin
from tessera.observability.evidence import (
    build_turn_evidence_bundle,
    list_recent_evidence_bundles,
    persist_evidence_bundle,
)
from tessera.observability.privacy import hash_identifier, sanitize_attributes
from tessera.observability.profiles import resolve_profile
from tessera.observability.verifier import verify_evidence_bundle
from tessera.settings import AssuranceLevel, ObservabilityProfile, get_settings

if TYPE_CHECKING:
    from pathlib import Path

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


def test_evidence_bundle_persistence_lists_recent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Evidence bundles persist as local redacted JSON and can be listed."""
    monkeypatch.setenv("TESSERA_OBS_PROFILE", "demo_premium")
    get_settings.cache_clear()
    root = tmp_path / "evidence"
    bundle = build_turn_evidence_bundle(
        conversation_id=UUID(int=10),
        turn_id=UUID(int=11),
        trace_id="trace-persist",
        model="gpt-test",
        language="fr",
        attributes={"language": "fr"},
    )

    path = persist_evidence_bundle(bundle, base_dir=root)
    recent = list_recent_evidence_bundles(base_dir=root)

    assert path.exists()
    assert recent[0]["evidence_id"] == bundle.evidence_id
    assert recent[0]["privacy_status"] == "redacted"


def test_decision_proof_validates_and_rejects_replay() -> None:
    """Sensitive action proofs bind tool, arguments, context, policy hash, and replay."""
    arguments: dict[str, object] = {"customer_id": "demo-customer-001"}
    context: dict[str, object] = {"language": "fr", "tool_name": "account_balance"}
    policy_hash = active_policy_hash()
    proof = issue_decision_proof(
        tool_name="account_balance",
        arguments=arguments,
        context=context,
        policy_hash=policy_hash,
        rule_id="tool.account_balance.allow",
        verdict="allowed",
        reason_code="guard_preflight_allowed",
    )

    first = validate_decision_proof(
        proof,
        tool_name="account_balance",
        arguments=arguments,
        context=context,
        policy_hash=policy_hash,
    )
    second = validate_decision_proof(
        proof,
        tool_name="account_balance",
        arguments=arguments,
        context=context,
        policy_hash=policy_hash,
    )

    assert first.valid is True
    assert second.valid is False
    assert second.reason_code == "proof_replayed"


def test_shadow_verifier_flags_sensitive_tool_without_proof() -> None:
    """Verifier catches the core V2 invariant: sensitive tools carry proof."""
    report = verify_evidence_bundle(
        {
            "evidence_id": "ev_test",
            "privacy_status": "redacted",
            "assurance_level": "L3",
            "signature": "hmac-sha256:test",
            "tool_calls": [{"tool_name": "account_balance"}],
            "retrieval_evidence": {"document_count": 0},
            "citation_evidence": [],
            "evidence_gaps": [],
        }
    )

    assert report.status == "fail"
    assert any(finding.code == "tool_without_proof" for finding in report.findings)


def test_assurance_twin_matrix_covers_profiles_and_languages() -> None:
    """Digital twin exposes cloud/on-prem/air-gapped coverage across languages."""
    scenarios = run_assurance_twin()
    keys = {(scenario.profile, scenario.language) for scenario in scenarios}

    assert ("cloud_gcp_regulated", "fr") in keys
    assert ("on_prem_standard", "de") in keys
    assert ("on_prem_airgapped", "en") in keys


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
    assert body["assurance"]["proof_slo_status"] == "degraded"
    assert body["llmops"]["role"] == "optional_llmops_cockpit"


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

"""Unit tests for EU AI Act compliance observability (ADR 0010, #76)."""

from __future__ import annotations

from tessera.observability.ai_act import AIActSignals, assess_compliance


def test_risk_class_is_limited() -> None:
    report = assess_compliance(AIActSignals())
    assert report.risk_class == "limited"
    assert report.n_obligations == 5


def test_fully_compliant() -> None:
    report = assess_compliance(
        AIActSignals(
            disclosure_enabled=True,
            escalation_available=True,
            audit_present=True,
            audit_chain_verified=True,
            data_governance_enabled=True,
        )
    )
    assert report.n_satisfied == 5
    assert report.compliance_rate == 1.0


def test_missing_disclosure_drops_compliance() -> None:
    report = assess_compliance(
        AIActSignals(
            disclosure_enabled=False,
            audit_present=True,
            audit_chain_verified=True,
        )
    )
    disclosure = next(o for o in report.obligations if o.name == "Transparency disclosure")
    assert disclosure.satisfied is False
    assert report.compliance_rate < 1.0


def test_broken_audit_chain_fails_traceability() -> None:
    report = assess_compliance(AIActSignals(audit_present=True, audit_chain_verified=False))
    trace = next(o for o in report.obligations if o.name.startswith("Logging"))
    assert trace.satisfied is False

"""Unit tests for the compliance posture assembly (image 07)."""

from __future__ import annotations

from tessera.observability import compliance as comp


def test_status_thresholds() -> None:
    assert comp._status(0.95) == "conformant"
    assert comp._status(0.75) == "partial"
    assert comp._status(0.40) == "non_conformant"


def test_risk_maps_from_status() -> None:
    assert comp._risk("conformant") == "low"
    assert comp._risk("partial") == "medium"
    assert comp._risk("non_conformant") == "high"


def test_compute_compliance_is_internally_consistent(monkeypatch) -> None:
    # Stub the signal read so the test is hermetic (no model / IO).
    values = {
        "ai_act": 1.0,
        "disclosure": 1.0,
        "conformance": 1.0,
        "citations": 0.95,
        "pii": 1.0,
        "refusal": 0.4,  # one non-conformant control
        "firewall": 0.75,  # partial
        "erasure": 0.8,  # partial
    }
    monkeypatch.setattr(comp, "_signal_values", lambda: values)
    report = comp.compute_compliance()

    # Every catalogue control whose signal is present is scored.
    assert report.n_controls == sum(1 for c in comp._CATALOGUE if c[3] in values)
    # Counts partition the controls.
    assert report.n_conformant + report.n_partial + report.n_non_conformant == report.n_controls
    # Score is the mean control value, on a 0..100 scale.
    assert 0 <= report.score <= 100
    # Obligations at risk = the partial/non-conformant controls.
    assert len(report.obligations) == report.n_partial + report.n_non_conformant
    assert len(report.non_conformities) == report.n_partial + report.n_non_conformant
    # Frameworks roll up only the controls they own.
    assert {f.code for f in report.frameworks} <= set(comp._FRAMEWORKS)
    for f in report.frameworks:
        assert f.n_conformant + f.n_partial + f.n_non_conformant > 0


def test_compute_compliance_all_conformant() -> None:
    values = dict.fromkeys(
        (
            "ai_act",
            "disclosure",
            "conformance",
            "citations",
            "pii",
            "refusal",
            "firewall",
            "erasure",
        ),
        1.0,
    )
    import pytest

    with pytest.MonkeyPatch.context() as m:
        m.setattr(comp, "_signal_values", lambda: values)
        report = comp.compute_compliance()
    assert report.n_non_conformant == 0
    assert report.n_partial == 0
    assert report.score == 100
    assert report.evidence_completeness == 1.0
    assert report.obligations == []

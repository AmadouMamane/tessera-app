"""Unit tests for AI-specific incident playbooks (ADR 0010, #115)."""

from __future__ import annotations

from tessera.observability.playbooks import PlaybookSignals, trigger_playbooks


def test_no_signals_no_playbooks() -> None:
    report = trigger_playbooks(PlaybookSignals(n_scores=10))
    assert report.n_triggered == 0


def test_hallucination_spike() -> None:
    report = trigger_playbooks(PlaybookSignals(low_score_rate=0.6, n_scores=10))
    incidents = {p.incident for p in report.playbooks}
    assert "Hallucination / quality spike" in incidents
    crit = next(p for p in report.playbooks if p.incident.startswith("Hallucination"))
    assert crit.severity == "critical"
    assert len(crit.steps) > 0


def test_low_score_requires_scores() -> None:
    # A high rate with no scores must not fire (no evidence).
    report = trigger_playbooks(PlaybookSignals(low_score_rate=0.9, n_scores=0))
    assert report.n_triggered == 0


def test_pii_leak_is_critical() -> None:
    report = trigger_playbooks(PlaybookSignals(pii_leak_rate=0.05))
    pii = next(p for p in report.playbooks if "PII" in p.incident)
    assert pii.severity == "critical"


def test_sorted_by_severity() -> None:
    report = trigger_playbooks(
        PlaybookSignals(low_score_rate=0.35, n_scores=10, cost_anomalies=1, pii_leak_rate=0.1)
    )
    severities = [p.severity for p in report.playbooks]
    rank = {"critical": 3, "high": 2, "medium": 1}
    assert severities == sorted(severities, key=lambda s: rank[s], reverse=True)


def test_cost_runaway_severity_scales() -> None:
    one = trigger_playbooks(PlaybookSignals(cost_anomalies=1))
    many = trigger_playbooks(PlaybookSignals(cost_anomalies=3))
    assert one.playbooks[0].severity == "medium"
    assert many.playbooks[0].severity == "high"

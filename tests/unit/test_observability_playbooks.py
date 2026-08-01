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
    # `n_turns` is now required for a bundle-derived rate to fire at all: 5 % of nothing is
    # not a leak, and the report used to have no way to say so.
    report = trigger_playbooks(PlaybookSignals(pii_leak_rate=0.05, n_turns=200))
    pii = next(p for p in report.playbooks if "PII" in p.incident)
    assert pii.severity == "critical"


def test_sorted_by_severity() -> None:
    report = trigger_playbooks(
        PlaybookSignals(
            low_score_rate=0.35, n_scores=10, cost_anomalies=1, pii_leak_rate=0.1, n_turns=200
        )
    )
    severities = [p.severity for p in report.playbooks]
    rank = {"critical": 3, "high": 2, "medium": 1}
    assert severities == sorted(severities, key=lambda s: rank[s], reverse=True)


def test_cost_runaway_severity_scales() -> None:
    one = trigger_playbooks(PlaybookSignals(cost_anomalies=1, n_turns=200))
    many = trigger_playbooks(PlaybookSignals(cost_anomalies=3, n_turns=200))
    assert one.playbooks[0].severity == "medium"
    assert many.playbooks[0].severity == "high"


def test_an_empty_window_is_not_a_quiet_fleet() -> None:
    """`n_triggered: 0` over nothing measured is a blind spot, not a clean bill.

    Only `low_score_rate` was gated on its sample size; the other three families defaulted to
    0.0 / 0.0 / 0, fired nothing, and the incident panel read "0 incidents". On 2026-08-01 the
    demo was in exactly that state — last conversation 2026-07-24, seven-day window — so every
    bundle-derived signal saw zero turns and the page reported peace.

    The digit is the same either way; `n_unmeasured` is what tells them apart.
    """
    empty = trigger_playbooks(PlaybookSignals())

    assert empty.n_triggered == 0
    assert empty.n_unmeasured == 4
    assert empty.unmeasured == ["hallucination", "jailbreak", "pii_leak", "cost"]


def test_a_measured_and_healthy_fleet_reports_nothing_unmeasured() -> None:
    """The other side of the same coin: 0 incidents over a real sample IS a clean bill."""
    healthy = trigger_playbooks(
        PlaybookSignals(
            low_score_rate=0.05,
            n_scores=120,
            jailbreak_success_rate=0.0,
            n_snapshots=3,
            pii_leak_rate=0.0,
            cost_anomalies=0,
            n_turns=400,
        )
    )

    assert healthy.n_triggered == 0
    assert healthy.n_unmeasured == 0
    assert healthy.unmeasured == []


def test_a_jailbreak_rate_with_no_snapshot_behind_it_does_not_fire() -> None:
    """`snapshots[-1]` on an empty list falls back to 0.0 upstream — a rate that never was.

    `redteam._SNAPSHOTS` is a process-local list, so a restart empties it. The route then reads
    `jailbreak_rate = 0.0` and, before this gate, that zero was indistinguishable from a measured
    zero: "no bypasses" from a probe that had not run since boot.
    """
    assert trigger_playbooks(PlaybookSignals(jailbreak_success_rate=0.9)).n_triggered == 0
    fired = trigger_playbooks(PlaybookSignals(jailbreak_success_rate=0.9, n_snapshots=1))
    assert fired.n_triggered == 1
    assert "jailbreak" not in fired.unmeasured

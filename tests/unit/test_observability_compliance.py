"""Unit tests for the compliance posture assembly (image 07)."""

from __future__ import annotations

from types import SimpleNamespace

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
    # Two args now: the as-of instant and the window length. The page shows a period
    # selector, so the posture it reports is the posture over the selected period.
    monkeypatch.setattr(comp, "_signal_values", lambda _at=None, _days=None: values)
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
        m.setattr(comp, "_signal_values", lambda _at=None, _days=None: values)
        report = comp.compute_compliance()
    assert report.n_non_conformant == 0
    assert report.n_partial == 0
    assert report.score == 100
    assert report.evidence_completeness == 1.0
    assert report.obligations == []


def test_legal_business_signals_project_only_manifest_legal_engagement(
    monkeypatch,
) -> None:
    agents = [
        SimpleNamespace(id="recouvrement", name="Recouvrement", observability=object()),
        SimpleNamespace(id="support-client", name="Support Client", observability=None),
    ]
    monkeypatch.setattr("tessera.agent.registry.list_agents", lambda: agents)
    monkeypatch.setattr(
        comp.business_capabilities_mod,
        "business_capability_aggregate",
        lambda **_kwargs: {
            "source": "local",
            "business_signals": [
                {
                    "key": "contact_window_compliance",
                    "engagement": "legal",
                    "value_pct": 100.0,
                    "status": "scored",
                    "reason": "contact_window_policy_passed",
                },
                {
                    "key": "action_governance",
                    "engagement": "none",
                    "value_pct": 100.0,
                    "status": "scored",
                    "reason": "artifact_actions_traceable",
                },
            ],
        },
    )

    rows = comp._legal_business_signals()

    assert len(rows) == 1
    row = rows[0]
    assert row.agent_id == "recouvrement"
    assert row.agent_name == "Recouvrement"
    assert row.key == "contact_window_compliance"
    assert row.value_pct == 100.0
    assert row.status == "scored"
    assert row.source == "local"
    assert row.href == "/agents/recouvrement/metier"


def test_posture_trend_buckets_real_scores(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    # Lower scores in the previous window, higher in the current → positive delta.
    rows: list[dict[str, object]] = []
    for day in range(comp._TREND_DAYS):  # current window, high scores
        rows.append(
            {
                "scored_at": (now - timedelta(days=day)).isoformat(),
                "metric": "faithfulness",
                "score": 0.9,
            }
        )
    for day in range(comp._TREND_DAYS, comp._TREND_DAYS * 2):  # previous window, low
        rows.append(
            {
                "scored_at": (now - timedelta(days=day)).isoformat(),
                "metric": "faithfulness",
                "score": 0.5,
            }
        )
    monkeypatch.setattr(comp, "read_scores", lambda **_kwargs: rows)
    series, delta = comp._posture_trend()
    assert len(series) > 1  # a real multi-point sparkline
    assert all(0.0 <= v <= 1.0 for v in series)
    assert delta is not None and delta > 0  # current period improved on the previous


def test_posture_trend_empty_log_yields_no_trend(monkeypatch) -> None:
    monkeypatch.setattr(comp, "read_scores", lambda **_kwargs: [])
    assert comp._posture_trend() == ([], None)

"""Unit tests for the continuous-improvement posture (image 09)."""

from __future__ import annotations

from tessera.observability import improvement as imp


def test_cause_and_action_labels_are_french() -> None:
    assert imp._cause_label("low_faithfulness", "fr") == "Risque hallucination"
    assert imp._cause_label("low_quality_de", "fr") == "Qualité multilingue"
    assert imp._action_label("low_faithfulness", 11, "fr") == "Curer 11 tours vers l'eval set"
    assert imp._action_label("low_quality_fr", 5, "fr") == "Corriger la qualité FR"


def test_compute_improvement_is_internally_consistent() -> None:
    report = imp.compute_improvement()
    # One opportunity per roadmap item; gains sum to the report total.
    assert report.n_active_actions == len(report.opportunities)
    assert round(sum(o.gain_pts for o in report.opportunities), 1) == report.potential_gain_pts
    # Opportunities are ranked 1..N and carry a French cause/action label.
    assert [o.rank for o in report.opportunities] == list(range(1, len(report.opportunities) + 1))
    # Coverage and debt are real, bounded values.
    assert 0.0 <= report.eval_coverage <= 1.0
    assert report.corpus_debt_days >= 0
    # The candidate carries gates whose pass flag is a bool.
    assert report.candidate is not None
    assert all(isinstance(g.passed, bool) for g in report.candidate.gates)

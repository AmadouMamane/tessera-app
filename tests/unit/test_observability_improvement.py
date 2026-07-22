"""Unit tests for the continuous-improvement posture (image 09)."""

from __future__ import annotations

from tessera.observability import improvement as imp


def test_cause_and_action_labels_are_french() -> None:
    assert imp._cause_label("low_faithfulness", "fr") == "Risque hallucination"
    assert imp._cause_label("low_quality_de", "fr") == "Qualité multilingue"
    assert imp._action_label("low_faithfulness", 11, "fr") == "Curer 11 tours vers l'eval set"
    assert imp._action_label("low_quality_fr", 5, "fr") == "Corriger la qualité FR"


def test_asof_far_future_is_available_and_consistent() -> None:
    """A far-future bound reads the full history and stays internally consistent.

    It is NOT asserted equal to live: the seam reads the recent ring live and the
    full history as-of (established SR-01 semantics, `read_scores`).
    """
    report = imp.compute_improvement(at="2999-01-01T00:00:00Z")
    assert report.n_active_actions == len(report.opportunities)
    assert 0.0 <= report.eval_coverage <= 1.0


def test_asof_epoch_reads_no_mined_data() -> None:
    """At 1970 no score, bundle or eval run exists — the mined posture is empty.

    Corpus freshness deliberately stays live (the corpus files carry no history),
    so only the run-derived fields are asserted empty.
    """
    report = imp.compute_improvement(at="1970-01-01T00:00:00Z")
    assert report.n_shadow_candidates == 0
    assert report.eval_coverage == 0.0
    # No score and no replay bundle at T: any surviving opportunity can only come
    # from the live corpus-freshness signal, never from mined telemetry.
    mined = ("eval set", "intents", "qualité", "Qualitaet", "quality")
    assert all(not any(m in o.action for m in mined) for o in report.opportunities)


def test_asof_malformed_reads_live() -> None:
    """A malformed instant must degrade to the live view, never raise."""
    assert imp.compute_improvement(at="not-a-date") == imp.compute_improvement()


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

"""Unit tests for telemetry → roadmap (ADR 0010, #124)."""

from __future__ import annotations

from tessera.observability.roadmap import RoadmapSignals, build_roadmap


def test_no_signals_no_items() -> None:
    report = build_roadmap(RoadmapSignals(n_turns=10))
    assert report.n_items == 0
    assert report.items == []


def test_each_signal_emits_one_item() -> None:
    report = build_roadmap(
        RoadmapSignals(
            n_turns=10,
            n_low_score=3,
            n_unknown_intent=2,
            n_coverage_gaps=1,
            n_stale_corpora=1,
        )
    )
    signals = {item.signal for item in report.items}
    assert signals == {"low_faithfulness", "coverage_gap", "unknown_intent", "stale_corpus"}


def test_ranked_by_severity_then_evidence() -> None:
    report = build_roadmap(RoadmapSignals(n_turns=10, n_low_score=5, n_unknown_intent=1))
    # 5/10 = 0.5 → high; 1/10 = 0.1 → medium. High comes first.
    assert report.items[0].signal == "low_faithfulness"
    assert report.items[0].severity == "high"
    assert report.items[1].severity == "medium"


def test_per_language_items() -> None:
    report = build_roadmap(RoadmapSignals(n_turns=10, languages_low={"de": 4, "fr": 1}))
    langs = [it for it in report.items if it.signal.startswith("low_quality_")]
    assert len(langs) == 2
    # de has more evidence → ranked above fr.
    assert langs[0].signal == "low_quality_de"


def test_stale_corpus_severity_by_count() -> None:
    one = build_roadmap(RoadmapSignals(n_turns=0, n_stale_corpora=1))
    two = build_roadmap(RoadmapSignals(n_turns=0, n_stale_corpora=2))
    assert one.items[0].severity == "medium"
    assert two.items[0].severity == "high"

"""Unit tests for GDPR erasure across telemetry (ADR 0010, #180)."""

from __future__ import annotations

from tessera.observability import erasure, replay as replay_mod
from tessera.observability.eval import scores as scores_mod
from tessera.observability.replay import ReplayBundle


def _bundle(conv: str) -> ReplayBundle:
    return ReplayBundle(
        bundle_id=f"b-{conv}",
        captured_at="2026-06-09T00:00:00+00:00",
        conversation_id=conv,
        language="fr",
        question="q",
        context="ctx",
        original_answer="a",
        original_model="llama3.2:3b",
        original_score=0.8,
    )


def test_footprint_counts_matches() -> None:
    bundles = [_bundle("c1"), _bundle("c2"), _bundle("c1")]
    scores = [{"conversation_id": "c1"}, {"conversation_id": "c3"}]
    fp = erasure.footprint("c1", bundles=bundles, scores=scores)
    assert fp.n_bundles == 2
    assert fp.n_scores == 1
    assert fp.total == 3


def test_coverage_distinct_conversations() -> None:
    bundles = [_bundle("c1"), _bundle("c2")]
    scores = [{"conversation_id": "c2"}, {"conversation_id": "c3"}]
    cov = erasure.coverage(bundles, scores)
    assert cov.n_conversations == 3
    assert cov.n_bundles == 2
    assert cov.n_scores == 2


def test_purge_telemetry_removes_from_buffers() -> None:
    # Seed the live buffers, purge one conversation, assert only it is gone.
    replay_mod.capture_bundle(
        question="q",
        context="ctx",
        original_answer="a",
        language="fr",
        original_score=0.8,
        original_model="m",
        conversation_id="erase-me",
    )
    replay_mod.capture_bundle(
        question="q",
        context="ctx",
        original_answer="a",
        language="fr",
        original_score=0.8,
        original_model="m",
        conversation_id="keep-me",
    )
    scores_mod._RECENT.append({"conversation_id": "erase-me", "score": 0.5})
    scores_mod._RECENT.append({"conversation_id": "keep-me", "score": 0.9})

    fp = erasure.purge_telemetry("erase-me")
    assert fp.n_bundles == 1
    assert fp.n_scores == 1

    remaining_convs = {b.conversation_id for b in replay_mod.recent_bundles()}
    assert "erase-me" not in remaining_convs
    assert "keep-me" in remaining_convs
    remaining_score_convs = {s.get("conversation_id") for s in scores_mod.recent_scores()}
    assert "erase-me" not in remaining_score_convs

    # Cleanup so we don't leak into other tests' buffers.
    erasure.purge_telemetry("keep-me")

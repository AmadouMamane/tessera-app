"""Unit tests for GDPR erasure across telemetry (ADR 0010, #180; ADR 0015 §Migration D)."""

from __future__ import annotations

import pytest

from tessera.observability import erasure, replay as replay_mod
from tessera.observability.eval import scores as scores_mod
from tessera.observability.replay import ReplayBundle
from tessera.observability.spine.adapters.base import SpineUnavailableError


@pytest.fixture(autouse=True)
def _offline_spine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every erasure test offline: the spine deletion is stubbed to a no-op by default.

    Tests that exercise the spine leg override this stub explicitly. The cache eviction is
    replaced by a spy so we can assert it fires without touching the process cache.
    """
    monkeypatch.setattr(erasure, "_spine_delete", lambda _conversation_id: 0)


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
    assert fp.n_spine == 0  # preview counts only local stores; the spine leg runs on purge


def test_coverage_distinct_conversations() -> None:
    bundles = [_bundle("c1"), _bundle("c2")]
    scores = [{"conversation_id": "c2"}, {"conversation_id": "c3"}]
    cov = erasure.coverage(bundles, scores)
    assert cov.n_conversations == 3
    assert cov.n_bundles == 2
    assert cov.n_scores == 2


def test_purge_telemetry_removes_from_buffers(monkeypatch: pytest.MonkeyPatch) -> None:
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

    # The spine reports one deleted trace; erasure must fold that into the footprint.
    monkeypatch.setattr(erasure, "_spine_delete", lambda _conversation_id: 1)
    fp = erasure.purge_telemetry("erase-me")
    assert fp.n_bundles == 1
    assert fp.n_scores == 1
    assert fp.n_spine == 1
    assert fp.spine_reached is True

    remaining_convs = {b.conversation_id for b in replay_mod.recent_bundles()}
    assert "erase-me" not in remaining_convs
    assert "keep-me" in remaining_convs
    remaining_score_convs = {s.get("conversation_id") for s in scores_mod.recent_scores()}
    assert "erase-me" not in remaining_score_convs

    # Cleanup so we don't leak into other tests' buffers.
    erasure.purge_telemetry("keep-me")


def test_purge_spine_evicts_cache_even_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(erasure, "reset_snapshot_cache", lambda: calls.append("evict"))
    monkeypatch.setattr(erasure, "_spine_delete", lambda _conversation_id: 3)

    deleted, reached = erasure.purge_spine("subject-x")
    assert deleted == 3
    assert reached is True
    assert calls == ["evict"]  # the read-through cache is always dropped


def test_purge_spine_unreachable_is_deferred_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(erasure, "reset_snapshot_cache", lambda: calls.append("evict"))

    def _down(_conversation_id: str) -> int:
        raise SpineUnavailableError("langfuse down")

    monkeypatch.setattr(erasure, "_spine_delete", _down)

    deleted, reached = erasure.purge_spine("subject-x")
    assert deleted == 0
    assert reached is False  # honesty: the spine leg is deferred, not silently "done"
    assert calls == ["evict"]  # cache still evicted so no snapshot resurrects an erased row

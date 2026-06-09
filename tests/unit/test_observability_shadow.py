"""Unit tests for shadow / mirror traffic (ADR 0010, #16)."""

from __future__ import annotations

import asyncio

import pytest

from tessera.observability import replay as replay_mod, shadow as shadow_mod
from tessera.observability.replay import ReplayBundle, ReplayResult


def _bundle(question: str, score: float, *, model: str = "llama3.2:3b") -> ReplayBundle:
    return ReplayBundle(
        bundle_id=question,
        captured_at="2026-06-09T00:00:00+00:00",
        conversation_id="c1",
        language="fr",
        question=question,
        context="ctx",
        original_answer="answer",
        original_model=model,
        original_score=score,
    )


@pytest.fixture
def _stub_replay(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    """Patch replay.replay to return a deterministic candidate score per bundle."""
    candidate_scores: dict[str, float] = {}

    async def fake_replay(bundle: ReplayBundle, *, model: str, **_: object) -> ReplayResult:
        cand = candidate_scores.get(bundle.question, bundle.original_score)
        return ReplayResult(
            bundle_id=bundle.bundle_id,
            original_model=bundle.original_model,
            original_score=bundle.original_score,
            candidate_model=model,
            candidate_answer="candidate",
            candidate_score=cand,
            score_delta=cand - bundle.original_score,
            similarity=0.7,
        )

    monkeypatch.setattr(replay_mod, "replay", fake_replay)
    return candidate_scores


def test_empty_bundles() -> None:
    report = asyncio.run(shadow_mod.run_shadow([], model="mistral:7b"))
    assert report.n_compared == 0
    assert report.wins == 0
    assert report.candidate_model == "mistral:7b"


def test_wins_losses_ties(_stub_replay: dict[str, float]) -> None:
    bundles = [_bundle("up", 0.5), _bundle("down", 0.9), _bundle("same", 0.8)]
    _stub_replay["up"] = 0.9  # +0.4 → win
    _stub_replay["down"] = 0.5  # -0.4 → loss
    _stub_replay["same"] = 0.81  # +0.01 within tie band → tie

    report = asyncio.run(shadow_mod.run_shadow(bundles, model="mistral:7b"))
    assert report.n_compared == 3
    assert report.wins == 1
    assert report.losses == 1
    assert report.ties == 1
    assert abs(report.mean_similarity - 0.7) < 1e-9


def test_limit_takes_newest(_stub_replay: dict[str, float]) -> None:
    bundles = [_bundle(f"q{i}", 0.8) for i in range(20)]
    report = asyncio.run(shadow_mod.run_shadow(bundles, model="mistral:7b", limit=5))
    assert report.n_compared == 5
    # The newest five questions are q15..q19.
    assert {c.question for c in report.comparisons} == {f"q{i}" for i in range(15, 20)}

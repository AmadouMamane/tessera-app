"""Unit tests for trace replay / regression-from-production (ADR 0010, #1)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from tessera.llm.router import ChatResponse
from tessera.observability import replay
from tessera.observability.eval.judge import JudgeVerdict

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from tessera.llm.router import ChatMessage


class _StubBackend:
    name = "stub"

    def __init__(self, content: str, model: str = "candidate-model") -> None:
        self._content = content
        self.model = model

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> ChatResponse:
        return ChatResponse(
            content=self._content,
            model=self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )

    def stream_chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        async def _gen() -> AsyncIterator[str]:
            yield self._content

        return _gen()


class _StubJudge:
    def __init__(self, score: float) -> None:
        self._score = score

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        return JudgeVerdict(metric=metric, score=self._score, rationale="", judge_model="stub")


def test_capture_and_retrieve() -> None:
    replay._BUNDLES.clear()
    bundle = replay.capture_bundle(
        question="q",
        context="c",
        original_answer="a",
        language="fr",
        original_score=0.5,
        original_model="m",
    )
    assert replay.get_bundle(bundle.bundle_id) is bundle
    assert replay.recent_bundles()[-1].bundle_id == bundle.bundle_id
    assert replay.get_bundle("missing") is None


def test_replay_computes_delta_and_similarity() -> None:
    bundle = replay.ReplayBundle(
        bundle_id="x",
        captured_at="t",
        conversation_id=None,
        language="fr",
        question="q",
        context="c",
        original_answer="hello world",
        original_model="m",
        original_score=0.4,
    )
    result = asyncio.run(
        replay.replay(
            bundle,
            model="candidate-model",
            judge=_StubJudge(0.9),
            backend=_StubBackend("hello world!"),
        )
    )
    assert result.candidate_model == "candidate-model"
    assert result.candidate_score == pytest.approx(0.9)
    assert result.score_delta == pytest.approx(0.5)
    assert 0.5 < result.similarity <= 1.0  # near-identical answer


def test_the_s2_capture_round_trips_through_the_durable_store() -> None:
    """XT-01 — the execution record survives the JSONL store byte-identically.

    The cassette lens reads bundles after a restart, so every S2 field must
    come back from disk exactly as captured, not only from process memory.
    """
    replay._BUNDLES.clear()
    captured = replay.capture_bundle(
        question="q",
        context="c",
        original_answer="a",
        language="fr",
        original_score=0.7,
        original_model="m",
        conversation_id="conv-s2",
        agent_id="support-client",
        turn_id="turn-s2",
        prompt_messages=[
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "CONTEXT…"},
        ],
        sampling={"temperature": 0.3, "top_p": 0.9},
        max_output_tokens=512,
        tool_calls=[
            {"name": "loan_simulate", "node": "simulator", "succeeded": True, "duration_ms": 12.5}
        ],
        node_starts={"router": 0.0, "simulator": 41.2},
        reporter_ms=850.4,
    )
    stored = [b for b in replay.persisted_bundles() if b.bundle_id == captured.bundle_id]
    assert len(stored) == 1
    bundle = stored[0]
    assert bundle.prompt_messages == captured.prompt_messages
    assert bundle.sampling == {"temperature": 0.3, "top_p": 0.9}
    assert bundle.max_output_tokens == 512
    assert bundle.tool_calls == [
        {"name": "loan_simulate", "node": "simulator", "succeeded": True, "duration_ms": 12.5}
    ]
    assert bundle.node_starts == {"router": 0.0, "simulator": 41.2}
    assert bundle.reporter_ms == pytest.approx(850.4)


def test_a_legacy_row_without_the_s2_fields_still_reads() -> None:
    """A bundle persisted before the S2 capture reads as "non capturé", never breaks."""
    legacy_row: dict[str, object] = {
        "bundle_id": "legacy",
        "captured_at": "2026-07-01T00:00:00+00:00",
        "conversation_id": None,
        "language": "fr",
        "question": "q",
        "context": "c",
        "original_answer": "a",
        "original_model": "m",
        "original_score": 0.5,
    }
    bundle = replay._row_to_bundle(legacy_row)
    assert bundle is not None
    assert bundle.prompt_messages is None
    assert bundle.sampling is None
    assert bundle.max_output_tokens is None
    assert bundle.tool_calls is None
    assert bundle.node_starts is None
    assert bundle.reporter_ms is None

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

"""Unit tests for ablation observability (ADR 0010, #81)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tessera.llm.router import ChatResponse
from tessera.observability.ablation import measure_ablation
from tessera.observability.eval.judge import JudgeVerdict

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.llm.router import ChatMessage


class _StubBackend:
    name = "stub"
    model = "stub-model"

    def __init__(self) -> None:
        self.contexts: list[str] = []

    async def chat(
        self, messages: Sequence[ChatMessage], *, temperature: float = 0.0, model: str = ""
    ) -> ChatResponse:
        # Record the context the ablation passed in (last user message).
        self.contexts.append(messages[-1].content)
        return ChatResponse(
            content="answer",
            model=model or self.model,
            input_tokens=1,
            output_tokens=1,
            finish_reason="stop",
        )


class _StubJudge:
    """Scores by a context-keyed table; empty context scores lowest."""

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    async def score(self, *, metric: str, question: str, answer: str, context: str) -> JudgeVerdict:
        key = "empty" if not context.strip() else "present"
        return JudgeVerdict(
            metric=metric, score=self._scores[key], rationale="", judge_model="stub-judge"
        )


def test_ablation_worth_relative_to_baseline() -> None:
    backend = _StubBackend()
    judge = _StubJudge({"empty": 0.3, "present": 0.7})
    report = asyncio.run(
        measure_ablation(
            question="q",
            context="chunk a\n\nchunk b",
            model="m",
            baseline=0.9,
            backend=backend,
            judge=judge,
        )
    )
    assert report.baseline == 0.9
    assert report.n_chunks == 2
    layers = {layer.layer: layer for layer in report.layers}
    # no-RAG drops to 0.3 → worth 0.6.
    assert abs(layers["no_rag"].score - 0.3) < 1e-9
    assert abs(layers["no_rag"].worth - 0.6) < 1e-9
    # no-rerank keeps the context (non-empty) → 0.7, worth 0.2.
    assert abs(layers["no_rerank"].worth - 0.2) < 1e-9


def test_no_rerank_reverses_chunk_order() -> None:
    backend = _StubBackend()
    judge = _StubJudge({"empty": 0.0, "present": 0.5})
    asyncio.run(
        measure_ablation(
            question="q",
            context="first\n\nsecond",
            model="m",
            baseline=0.8,
            backend=backend,
            judge=judge,
        )
    )
    # Second generation (no-rerank) reverses the chunk order in the context.
    no_rerank_ctx = backend.contexts[1]
    assert no_rerank_ctx.index("second") < no_rerank_ctx.index("first")

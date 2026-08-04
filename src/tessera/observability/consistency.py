"""Self-consistency uncertainty (ADR 0010, idea #18).

A free hallucination signal: ask the model the same grounded question several
times at non-zero temperature and measure how much the answers *agree*. Stable
answers (high pairwise similarity) mean the model is confident; answers that
scatter mean it is guessing. Uncertainty is ``1 - mean pairwise similarity`` —
complementary to the LLM judge and to token-level signals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tessera.llm.ceiling import resolve_spend_model
from tessera.llm.router import ChatMessage, backend_for_model
from tessera.retrieval.embeddings import embed

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.llm.router import ChatBackend

__all__ = ["ConsistencyReport", "measure_consistency"]

_SAMPLE_SYSTEM = (
    "You are a banking support assistant. Answer the QUESTION using ONLY the "
    "CONTEXT. Be precise and do not invent facts not present in the context."
)
_DEFAULT_SAMPLES = 3
_SAMPLE_TEMPERATURE = 0.7


@dataclass(frozen=True, slots=True)
class ConsistencyReport:
    """Self-consistency of repeated answers to the same question."""

    samples: int
    consistency: float  # mean pairwise cosine similarity, 0..1
    uncertainty: float  # 1 - consistency
    answers: list[str]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def measure_consistency(
    *,
    question: str,
    context: str,
    model: str,
    samples: int = _DEFAULT_SAMPLES,
    backend: ChatBackend | None = None,
) -> ConsistencyReport:
    """Sample the answer ``samples`` times and measure semantic agreement.

    Args:
        question: The user question.
        context: The grounding context.
        model: The model to sample from.
        samples: Number of samples to draw (>= 2 for a meaningful spread).
        backend: Generation backend; defaults to ``backend_for_model(model)``.

    Returns:
        A :class:`ConsistencyReport`.
    """
    model = await resolve_spend_model(caller="observability.consistency", model=model)
    generator = backend or backend_for_model(model)
    messages = [
        ChatMessage(role="system", content=_SAMPLE_SYSTEM),
        ChatMessage(role="user", content=f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
    ]
    answers: list[str] = []
    for _ in range(samples):
        response = await generator.chat(messages, temperature=_SAMPLE_TEMPERATURE, model=model)
        answers.append(response.content)

    vectors = await embed(answers)
    sims = [
        _cosine(vectors[i], vectors[j])
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
    ]
    consistency = sum(sims) / len(sims) if sims else 1.0
    return ConsistencyReport(
        samples=len(answers),
        consistency=consistency,
        uncertainty=max(0.0, 1.0 - consistency),
        answers=answers,
    )

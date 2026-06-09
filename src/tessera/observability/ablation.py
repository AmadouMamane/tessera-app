"""Ablation observability (ADR 0010, idea #81).

A RAG stack is a tower of layers — retrieval, reranking, memory — each assumed to
earn its place. Ablation puts a number on that assumption: re-answer a captured
turn with one layer knocked out, re-judge, and the drop in faithfulness *is* that
layer's contribution. If removing the reranker costs nothing, the reranker is
dead weight; if removing retrieval barely moves the score, the model was
answering from parametric memory and the grounding was theatre.

This module re-runs a captured turn under two ablations and re-judges each:

* **no-RAG** — answer with an empty context (the model is on its own);
* **no-rerank** — present the same chunks in reversed order, so the best chunk is
  no longer first (the reranker's ordering benefit is removed).

Each layer's *worth* is ``baseline − ablated_score``. Generation and judging
reuse the sovereign local backend and :class:`LLMJudge`, so the whole thing runs
zero-egress.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.llm.router import ChatMessage, backend_for_model
from tessera.observability.eval.judge import FAITHFULNESS, LLMJudge

if TYPE_CHECKING:
    from tessera.llm.router import ChatBackend
    from tessera.observability.eval.judge import Judge

__all__ = ["AblationLayer", "AblationReport", "measure_ablation"]

_ANSWER_SYSTEM = (
    "You are a banking support assistant. Answer the QUESTION using ONLY the "
    "CONTEXT. Be precise and do not invent facts not present in the context."
)


@dataclass(frozen=True, slots=True)
class AblationLayer:
    """The quality of a turn with one layer removed."""

    layer: str  # "no_rag" | "no_rerank"
    score: float
    worth: float  # baseline minus this score (positive = the layer helped)


@dataclass(frozen=True, slots=True)
class AblationReport:
    """Per-layer contribution of the RAG stack for one captured turn."""

    baseline: float
    model: str
    n_chunks: int
    layers: list[AblationLayer] = field(default_factory=list)


async def _answer(backend: ChatBackend, *, question: str, context: str, model: str) -> str:
    messages = [
        ChatMessage(role="system", content=_ANSWER_SYSTEM),
        ChatMessage(role="user", content=f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
    ]
    response = await backend.chat(messages, temperature=0.0, model=model)
    return response.content


async def measure_ablation(
    *,
    question: str,
    context: str,
    model: str,
    baseline: float,
    backend: ChatBackend | None = None,
    judge: Judge | None = None,
) -> AblationReport:
    """Re-answer a captured turn under no-RAG and no-rerank ablations.

    Args:
        question: The user question.
        context: The grounding context (chunks joined by blank lines).
        model: The model id to regenerate with.
        baseline: The faithfulness the full stack earned (the reference).
        backend: Generation backend; defaults to ``backend_for_model(model)``.
        judge: Judge for scoring; defaults to :class:`LLMJudge`.

    Returns:
        An :class:`AblationReport` with each layer's worth relative to baseline.
    """
    chunks = [c for c in context.split("\n\n") if c.strip()]
    generator = backend or backend_for_model(model)
    active_judge: Judge = judge or LLMJudge()

    async def _score(ablated_context: str) -> float:
        answer = await _answer(generator, question=question, context=ablated_context, model=model)
        verdict = await active_judge.score(
            metric=FAITHFULNESS, question=question, answer=answer, context=ablated_context
        )
        return verdict.score

    no_rag_score = await _score("")
    # no-rerank: reverse chunk order so the best-ranked chunk is no longer first.
    no_rerank_score = await _score("\n\n".join(reversed(chunks)))

    layers = [
        AblationLayer(layer="no_rag", score=no_rag_score, worth=baseline - no_rag_score),
        AblationLayer(layer="no_rerank", score=no_rerank_score, worth=baseline - no_rerank_score),
    ]
    return AblationReport(baseline=baseline, model=model, n_chunks=len(chunks), layers=layers)

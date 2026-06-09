"""Deterministic trace replay / regression-from-production (ADR 0010, #1).

Every grounded production turn is captured as a :class:`ReplayBundle` — enough
to re-run it: the question, the retrieved context, the original answer, and the
faithfulness score it earned. :func:`replay` then re-generates an answer for the
same ``(question, context)`` with a *candidate* model, re-judges it, and reports
the score delta and a textual similarity. A real conversation thereby becomes a
regression test against a model or prompt change.

The capture store is an in-process ring buffer (a convenience view for the
dashboard, not the system of record). Replays are driven through the API/UI,
which is why no separate CLI process reads the buffer.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from tessera.llm.router import ChatMessage, backend_for_model
from tessera.observability.eval.judge import FAITHFULNESS, LLMJudge

if TYPE_CHECKING:
    from tessera.llm.router import ChatBackend
    from tessera.observability.eval.judge import Judge
    from tessera.observability.lineage import Lineage

__all__ = [
    "ReplayBundle",
    "ReplayResult",
    "capture_bundle",
    "get_bundle",
    "purge_conversation",
    "recent_bundles",
    "replay",
]

_BUNDLES: deque[ReplayBundle] = deque(maxlen=100)

_ANSWER_SYSTEM = (
    "You are a banking support assistant. Answer the QUESTION using ONLY the "
    "CONTEXT. Be precise and do not invent facts not present in the context."
)


@dataclass(frozen=True, slots=True)
class ReplayBundle:
    """A captured turn, replayable against a new model/prompt."""

    bundle_id: str
    captured_at: str
    conversation_id: str | None
    language: str
    question: str
    context: str
    original_answer: str
    original_model: str
    original_score: float
    lineage: Lineage | None = None
    latency_ms: dict[str, float] | None = None


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """The outcome of replaying a bundle against a candidate model."""

    bundle_id: str
    original_model: str
    original_score: float
    candidate_model: str
    candidate_answer: str
    candidate_score: float
    score_delta: float  # candidate minus original (positive = improvement)
    similarity: float  # 0..1 textual similarity to the original answer


def capture_bundle(
    *,
    question: str,
    context: str,
    original_answer: str,
    language: str,
    original_score: float,
    original_model: str,
    conversation_id: str | None = None,
    lineage: Lineage | None = None,
    latency_ms: dict[str, float] | None = None,
) -> ReplayBundle:
    """Capture a grounded turn for later replay; returns the stored bundle."""
    bundle = ReplayBundle(
        bundle_id=uuid.uuid4().hex,
        captured_at=datetime.now(UTC).isoformat(),
        conversation_id=conversation_id,
        language=language,
        question=question,
        context=context,
        original_answer=original_answer,
        original_model=original_model,
        original_score=original_score,
        lineage=lineage,
        latency_ms=latency_ms,
    )
    _BUNDLES.append(bundle)
    return bundle


def recent_bundles() -> list[ReplayBundle]:
    """Return the captured bundles (newest last)."""
    return list(_BUNDLES)


def get_bundle(bundle_id: str) -> ReplayBundle | None:
    """Return the bundle with ``bundle_id`` if still in the buffer."""
    return next((b for b in _BUNDLES if b.bundle_id == bundle_id), None)


def purge_conversation(conversation_id: str) -> int:
    """Drop all captured bundles for a conversation (GDPR erasure, #180).

    Returns the number of bundles removed, so erasure reaches the replay
    telemetry and not only the system of record.
    """
    kept = [b for b in _BUNDLES if b.conversation_id != conversation_id]
    removed = len(_BUNDLES) - len(kept)
    _BUNDLES.clear()
    _BUNDLES.extend(kept)
    return removed


async def replay(
    bundle: ReplayBundle,
    *,
    model: str,
    judge: Judge | None = None,
    backend: ChatBackend | None = None,
) -> ReplayResult:
    """Re-run ``bundle`` against ``model`` and diff against the original.

    Args:
        bundle: The captured turn to replay.
        model: The candidate model id to generate the new answer with.
        judge: Judge for scoring; defaults to the configured :class:`LLMJudge`.
        backend: Generation backend; defaults to ``backend_for_model(model)``.

    Returns:
        A :class:`ReplayResult` with the candidate answer, its faithfulness
        score, the delta versus the original, and textual similarity.
    """
    generator = backend or backend_for_model(model)
    messages = [
        ChatMessage(role="system", content=_ANSWER_SYSTEM),
        ChatMessage(
            role="user",
            content=f"CONTEXT:\n{bundle.context}\n\nQUESTION:\n{bundle.question}",
        ),
    ]
    response = await generator.chat(messages, temperature=0.0, model=model)
    candidate_answer = response.content

    active_judge: Judge = judge or LLMJudge()
    verdict = await active_judge.score(
        metric=FAITHFULNESS,
        question=bundle.question,
        answer=candidate_answer,
        context=bundle.context,
    )
    similarity = SequenceMatcher(None, bundle.original_answer, candidate_answer).ratio()
    return ReplayResult(
        bundle_id=bundle.bundle_id,
        original_model=bundle.original_model,
        original_score=bundle.original_score,
        candidate_model=response.model,
        candidate_answer=candidate_answer,
        candidate_score=verdict.score,
        score_delta=verdict.score - bundle.original_score,
        similarity=similarity,
    )

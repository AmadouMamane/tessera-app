"""Multi-turn contradiction detection (ADR 0010, idea #30).

Over a conversation, an agent can quietly contradict itself: "your card is
blocked" on turn 2, "your card is active" on turn 5. A single-turn faithfulness
score never catches this — it needs the *session* in view (ADR 0007 memory).

The signal here is geometric. Embed every turn's question and answer. A pair of
turns that talk about the **same thing** (high question similarity) but give
**divergent answers** (low answer similarity) is a candidate contradiction. It is
a cheap, model-agnostic screen that surfaces pairs for a judge or a human to
confirm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.retrieval.embeddings import embed

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

__all__ = ["ContradictionPair", "ContradictionReport", "detect_contradictions"]

_TOPIC_THRESHOLD = 0.6  # questions this similar are "about the same thing"
_ANSWER_THRESHOLD = 0.4  # answers this dissimilar disagree


@dataclass(frozen=True, slots=True)
class ContradictionPair:
    """Two turns that discuss the same topic but disagree."""

    i: int
    j: int
    topic_similarity: float
    answer_similarity: float
    question_i: str
    question_j: str


@dataclass(frozen=True, slots=True)
class ContradictionReport:
    """Contradiction screen over the turns of one conversation."""

    n_turns: int
    n_pairs_checked: int
    n_contradictions: int
    contradictions: list[ContradictionPair] = field(default_factory=list)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


async def detect_contradictions(
    turns: Sequence[tuple[str, str]],
    *,
    topic_threshold: float = _TOPIC_THRESHOLD,
    answer_threshold: float = _ANSWER_THRESHOLD,
    embedder: Callable[[Sequence[str]], Awaitable[list[list[float]]]] | None = None,
) -> ContradictionReport:
    """Detect self-contradictions across ``(question, answer)`` turns.

    Args:
        turns: The conversation's turns, oldest first.
        topic_threshold: Minimum question cosine for two turns to share a topic.
        answer_threshold: Maximum answer cosine for two turns to disagree.
        embedder: Async embedding function; defaults to the retrieval embedder.

    Returns:
        A :class:`ContradictionReport` listing the flagged turn pairs.
    """
    embed_fn = embedder or embed
    n_turns = len(turns)
    if n_turns < 2:  # noqa: PLR2004 — a single turn cannot contradict itself
        return ContradictionReport(n_turns=n_turns, n_pairs_checked=0, n_contradictions=0)

    questions = [q for q, _ in turns]
    answers = [a for _, a in turns]
    q_vectors = await embed_fn(questions)
    a_vectors = await embed_fn(answers)

    pairs: list[ContradictionPair] = []
    checked = 0
    for i in range(n_turns):
        for j in range(i + 1, n_turns):
            checked += 1
            topic = _cosine(q_vectors[i], q_vectors[j])
            if topic < topic_threshold:
                continue
            answer_sim = _cosine(a_vectors[i], a_vectors[j])
            if answer_sim > answer_threshold:
                continue
            pairs.append(
                ContradictionPair(
                    i=i,
                    j=j,
                    topic_similarity=topic,
                    answer_similarity=answer_sim,
                    question_i=questions[i],
                    question_j=questions[j],
                )
            )

    return ContradictionReport(
        n_turns=n_turns,
        n_pairs_checked=checked,
        n_contradictions=len(pairs),
        contradictions=pairs,
    )

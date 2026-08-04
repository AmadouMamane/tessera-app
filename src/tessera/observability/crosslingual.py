"""Cross-lingual answer consistency (ADR 0010, idea #70).

Tessera answers the same question in French, German, and English. The same
grounded question should yield the *same answer* in every language — if the
German answer quietly says something the French one doesn't, one of them is
wrong. This is differential testing across languages: re-answer a captured turn
in each language, embed the answers with a multilingual embedder, and measure how
much they agree. Low agreement flags a cross-lingual divergence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tessera.llm.ceiling import resolve_spend_model
from tessera.llm.router import ChatMessage, backend_for_model
from tessera.retrieval.embeddings import embed

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from tessera.llm.router import ChatBackend

__all__ = ["CrossLingualReport", "measure_crosslingual"]

_LANGUAGES: tuple[str, ...] = ("fr", "de", "en")
_LANGUAGE_NAMES = {"fr": "French", "de": "German", "en": "English"}
_CONSISTENCY_THRESHOLD = 0.6  # min pairwise cosine to count as consistent


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass(frozen=True, slots=True)
class CrossLingualReport:
    """Cross-lingual agreement of answers to the same grounded question."""

    languages: list[str]
    consistency: float  # mean pairwise cosine
    min_similarity: float  # weakest pair (the divergence)
    consistent: bool
    answers: dict[str, str] = field(default_factory=dict)


async def measure_crosslingual(
    *,
    question: str,
    context: str,
    model: str,
    languages: Sequence[str] = _LANGUAGES,
    backend: ChatBackend | None = None,
    embedder: Callable[[Sequence[str]], Awaitable[list[list[float]]]] | None = None,
) -> CrossLingualReport:
    """Answer ``question`` in each language and measure cross-lingual agreement.

    Args:
        question: The user question.
        context: The grounding context (shared across languages).
        model: The model to generate with.
        languages: Language codes to answer in.
        backend: Generation backend; defaults to ``backend_for_model(model)``.
        embedder: Async (ideally multilingual) embedder; defaults to retrieval's.

    Returns:
        A :class:`CrossLingualReport`.
    """
    model = await resolve_spend_model(caller="observability.crosslingual", model=model)
    generator = backend or backend_for_model(model)
    embed_fn = embedder or embed

    answers: dict[str, str] = {}
    for lang in languages:
        name = _LANGUAGE_NAMES.get(lang, lang)
        messages = [
            ChatMessage(
                role="system",
                content=(
                    f"You are a banking support assistant. Answer in {name} using ONLY "
                    "the CONTEXT. Be precise and do not invent facts."
                ),
            ),
            ChatMessage(role="user", content=f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
        ]
        response = await generator.chat(messages, temperature=0.0, model=model)
        answers[lang] = response.content

    vectors = await embed_fn(list(answers.values()))
    sims = [
        _cosine(vectors[i], vectors[j])
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
    ]
    consistency = sum(sims) / len(sims) if sims else 1.0
    min_sim = min(sims) if sims else 1.0
    return CrossLingualReport(
        languages=list(languages),
        consistency=consistency,
        min_similarity=min_sim,
        consistent=min_sim >= _CONSISTENCY_THRESHOLD,
        answers=answers,
    )

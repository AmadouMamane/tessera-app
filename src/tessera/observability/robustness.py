"""Robustness under input noise (ADR 0010, idea #46).

Real users mistype, paste OCR noise, and shout in caps; attackers swap in
unicode homoglyphs. A trustworthy agent should answer a noisy question much like
a clean one. This module perturbs a captured question (typos, Cyrillic
homoglyphs, uppercasing), re-answers each variant, and measures stability: how
similar the answers stay and whether faithfulness drops.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from tessera.llm.router import ChatMessage, backend_for_model
from tessera.observability.eval.judge import FAITHFULNESS, LLMJudge

if TYPE_CHECKING:
    from collections.abc import Callable

    from tessera.llm.router import ChatBackend
    from tessera.observability.eval.judge import Judge

__all__ = ["PerturbationResult", "RobustnessReport", "measure_robustness", "perturbations"]

_ANSWER_SYSTEM = (
    "You are a banking support assistant. Answer the QUESTION using ONLY the "
    "CONTEXT. Be precise and do not invent facts not present in the context."
)

# Latin → visually-identical Cyrillic letters (a classic homoglyph attack).
_HOMOGLYPHS = {"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х", "y": "у"}  # noqa: RUF001  intentional Cyrillic look-alikes


def _typos(text: str) -> str:
    """Swap two adjacent characters near the middle (a deterministic typo)."""
    i = len(text) // 2
    if i + 1 >= len(text):
        return text
    return text[:i] + text[i + 1] + text[i] + text[i + 2 :]


def _homoglyphs(text: str) -> str:
    """Replace lowercase Latin letters with Cyrillic look-alikes."""
    return "".join(_HOMOGLYPHS.get(ch, ch) for ch in text)


def _uppercase(text: str) -> str:
    """Shout the question in uppercase."""
    return text.upper()


def perturbations() -> dict[str, Callable[[str], str]]:
    """Return the named perturbation functions."""
    return {"typos": _typos, "homoglyph": _homoglyphs, "uppercase": _uppercase}


@dataclass(frozen=True, slots=True)
class PerturbationResult:
    """Stability of the answer under one perturbation."""

    kind: str
    perturbed_question: str
    similarity: float  # vs the baseline answer, 0..1
    faithfulness: float


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    """How stable the agent is under input noise."""

    baseline_faithfulness: float
    mean_similarity: float
    min_faithfulness: float
    results: list[PerturbationResult]


async def _answer(backend: ChatBackend, question: str, context: str, model: str) -> str:
    messages = [
        ChatMessage(role="system", content=_ANSWER_SYSTEM),
        ChatMessage(role="user", content=f"CONTEXT:\n{context}\n\nQUESTION:\n{question}"),
    ]
    response = await backend.chat(messages, temperature=0.0, model=model)
    return response.content


async def measure_robustness(
    *,
    question: str,
    context: str,
    model: str,
    backend: ChatBackend | None = None,
    judge: Judge | None = None,
) -> RobustnessReport:
    """Answer the clean question and each perturbed variant, and score stability."""
    generator = backend or backend_for_model(model)
    active_judge: Judge = judge or LLMJudge()

    baseline = await _answer(generator, question, context, model)
    baseline_faith = (
        await active_judge.score(
            metric=FAITHFULNESS, question=question, answer=baseline, context=context
        )
    ).score

    results: list[PerturbationResult] = []
    faiths: list[float] = [baseline_faith]
    sims: list[float] = []
    for kind, fn in perturbations().items():
        perturbed = fn(question)
        answer = await _answer(generator, perturbed, context, model)
        similarity = SequenceMatcher(None, baseline, answer).ratio()
        faith = (
            await active_judge.score(
                metric=FAITHFULNESS, question=perturbed, answer=answer, context=context
            )
        ).score
        sims.append(similarity)
        faiths.append(faith)
        results.append(
            PerturbationResult(
                kind=kind, perturbed_question=perturbed, similarity=similarity, faithfulness=faith
            )
        )

    return RobustnessReport(
        baseline_faithfulness=baseline_faith,
        mean_similarity=sum(sims) / len(sims) if sims else 1.0,
        min_faithfulness=min(faiths),
        results=results,
    )

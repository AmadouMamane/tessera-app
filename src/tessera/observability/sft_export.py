"""Traces as training data (ADR 0010, idea #122).

There are two flywheels in this system. The *eval* flywheel curates **failures**
into the regression set (``eval/failures/``) so the agent stops regressing. This
is the *improvement* flywheel: it curates the **successes** — production turns the
judge scored highly — into supervised fine-tuning data for the sovereign local
model, so the on-prem path keeps getting better from its own best work, with no
data leaving the box.

A captured turn maps cleanly onto an instruction-tuning record: the grounding
context and question are the input, the high-scoring answer is the target. Only
turns at or above ``min_score`` are eligible, so the dataset is built from
answers the judge already validated. The builder is pure over turn tuples; the
endpoint feeds it captured bundles and returns a redacted preview plus the
dataset statistics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = ["SFTDataset", "SFTRecord", "build_sft_dataset"]

# A turn must score at least this to be eligible as a positive SFT example.
_DEFAULT_MIN_SCORE = 0.80
_INSTRUCTION = (
    "You are a banking support assistant. Answer the QUESTION using ONLY the "
    "CONTEXT. Be precise and do not invent facts not present in the context."
)
_PREVIEW = 120


@dataclass(frozen=True, slots=True)
class SFTRecord:
    """One supervised fine-tuning example distilled from a good trace."""

    instruction: str
    input: str
    output: str
    language: str
    score: float


@dataclass(frozen=True, slots=True)
class SFTDataset:
    """An SFT dataset built from curated high-scoring traces."""

    n_total: int
    n_eligible: int
    min_score: float
    by_language: dict[str, int]
    samples: list[SFTRecord] = field(default_factory=list)


def build_sft_dataset(
    turns: Iterable[tuple[str, str, str, str, float]],
    *,
    min_score: float = _DEFAULT_MIN_SCORE,
    sample_limit: int = 10,
) -> SFTDataset:
    """Distil high-scoring turns into an instruction-tuning dataset.

    Args:
        turns: ``(question, context, answer, language, score)`` tuples.
        min_score: Minimum faithfulness for a turn to be eligible.
        sample_limit: Maximum redacted records to return in ``samples``.

    Returns:
        An :class:`SFTDataset` with eligibility counts and a redacted sample.
    """
    n_total = 0
    n_eligible = 0
    by_language: dict[str, int] = {}
    samples: list[SFTRecord] = []
    for question, context, answer, language, score in turns:
        n_total += 1
        if score < min_score or not answer.strip():
            continue
        n_eligible += 1
        by_language[language] = by_language.get(language, 0) + 1
        if len(samples) < sample_limit:
            samples.append(
                SFTRecord(
                    instruction=_INSTRUCTION,
                    input=f"CONTEXT:\n{context[:_PREVIEW]}\n\nQUESTION:\n{question[:_PREVIEW]}",
                    output=answer[:_PREVIEW],
                    language=language,
                    score=score,
                )
            )

    return SFTDataset(
        n_total=n_total,
        n_eligible=n_eligible,
        min_score=min_score,
        by_language=by_language,
        samples=samples,
    )

"""Context truncation / overflow observability (ADR 0010, idea #89).

When a turn's assembled context exceeds the model's input window, something has
to be dropped — and if the dropped chunk was the one that actually answered the
question, the agent silently loses its grounding. This module estimates each
turn's context size against a configured window budget, reports how many trailing
chunks would be truncated to fit, and aggregates the overflow rate so a context
that routinely overruns the window is visible (it complements #31's per-node
token-budget split).

Token counts reuse :func:`tessera.observability.cost_anomaly.estimate_tokens`, so
the estimate matches the cost view exactly. It is pure: the route supplies the
already-split chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tessera.observability.cost_anomaly import estimate_tokens

__all__ = ["OverflowReport", "TurnOverflow", "analyze_overflow"]

# Default input window (tokens). Conservative vs Llama 3.3 70B / frontier models;
# overridable per call so a smaller-window deployment can tighten the check.
_DEFAULT_WINDOW_TOKENS = 8192
# Reserve headroom for the system prompt, question, and the answer being generated.
_RESERVED_TOKENS = 1024


@dataclass(frozen=True, slots=True)
class TurnOverflow:
    """The context-budget picture for a single turn."""

    question: str
    n_chunks: int
    context_tokens: int
    n_dropped: int  # trailing chunks that would be truncated to fit the budget
    overflowed: bool


@dataclass(frozen=True, slots=True)
class OverflowReport:
    """Aggregate context-overflow statistics across turns."""

    n_turns: int
    n_overflowed: int
    overflow_rate: float
    window_tokens: int
    usable_tokens: int
    max_context_tokens: int
    turns: list[TurnOverflow] = field(default_factory=list)


def _assess_turn(question: str, chunks: list[str], usable: int) -> TurnOverflow:
    """Walk the chunks in order, counting which trailing ones overflow ``usable``."""
    total = 0
    used = 0
    for chunk in chunks:
        total += estimate_tokens(chunk)
        if total <= usable:
            used += 1
    n_dropped = len(chunks) - used
    return TurnOverflow(
        question=question,
        n_chunks=len(chunks),
        context_tokens=total,
        n_dropped=n_dropped,
        overflowed=n_dropped > 0,
    )


def analyze_overflow(
    turns: list[tuple[str, list[str]]], *, window_tokens: int = _DEFAULT_WINDOW_TOKENS
) -> OverflowReport:
    """Assess how many turns overrun the input window and lose context.

    Args:
        turns: ``(question, context_chunks)`` per captured turn, chunks in the
            order they were assembled into the prompt.
        window_tokens: The model's input window; the usable budget subtracts a
            fixed reservation for the system prompt, question, and answer.

    Returns:
        An :class:`OverflowReport` with the per-turn overflow and the rate.
    """
    usable = max(1, window_tokens - _RESERVED_TOKENS)
    rows = [_assess_turn(q, chunks, usable) for q, chunks in turns]
    n_overflowed = sum(1 for r in rows if r.overflowed)
    max_tokens = max((r.context_tokens for r in rows), default=0)
    return OverflowReport(
        n_turns=len(rows),
        n_overflowed=n_overflowed,
        overflow_rate=n_overflowed / len(rows) if rows else 0.0,
        window_tokens=window_tokens,
        usable_tokens=usable,
        max_context_tokens=max_tokens,
        turns=rows,
    )

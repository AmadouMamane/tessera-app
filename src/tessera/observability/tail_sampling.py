"""Tail-based sampling policy (ADR 0010, idea #32).

Head-based sampling decides whether to keep a trace *before* it runs, so it keeps
a uniform random slice — and throws away exactly the rare, slow, low-quality
turns you most want to see. Tail-based sampling decides *after* the turn
completes, when its outcome is known, so it can keep **100 % of the interesting
tail** (slow, low faithfulness, error) and sample only the boring head.

This module is the *policy*, evaluated over captured turns. :func:`decide`
classifies one trace; :func:`analyze_sampling` aggregates the policy over the
ring buffer and reports retention — proving the tail is fully retained while the
head is thinned to the base rate. The head decision is a deterministic hash of
the trace id (not RNG), so the same trace always gets the same verdict and the
retention figures are reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.observability.replay import ReplayBundle

__all__ = ["SamplingDecision", "TailSamplingReport", "analyze_sampling", "decide"]

# Defaults. A turn slower than this, or scoring below this faithfulness, is tail.
_DEFAULT_SLOW_MS = 2500.0
_DEFAULT_SCORE_THRESHOLD = 0.80
# Fraction of the (boring) head we keep for baseline visibility.
_DEFAULT_BASE_RATE = 0.10
_SNIPPET = 80


@dataclass(frozen=True, slots=True)
class SamplingDecision:
    """The keep/drop verdict for one trace and why."""

    keep: bool
    tail: bool  # whether the trace is in the interesting tail
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TailSamplingReport:
    """Retention of the tail policy over a batch of captured traces."""

    n_traces: int
    n_tail: int
    n_head: int
    n_kept: int
    n_dropped: int
    retention_rate: float  # kept / total
    tail_retention_rate: float  # kept-tail / tail (the guarantee — should be 1.0)
    base_rate: float
    n_slow: int
    n_low_score: int
    slow_threshold_ms: float
    score_threshold: float


def _keep_head(trace_id: str, base_rate: float) -> bool:
    """Deterministically keep a fraction ``base_rate`` of head traces by id hash."""
    if base_rate <= 0:
        return False
    if base_rate >= 1:
        return True
    digest = hashlib.sha256(trace_id.encode("utf-8")).digest()
    # Map the first 8 bytes to a uniform [0, 1) and keep when below the rate.
    bucket = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return bucket < base_rate


def decide(
    *,
    trace_id: str,
    latency_ms: float,
    score: float,
    base_rate: float = _DEFAULT_BASE_RATE,
    slow_threshold_ms: float = _DEFAULT_SLOW_MS,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
) -> SamplingDecision:
    """Decide whether to keep one trace under the tail-sampling policy.

    A trace is tail (always kept) when it is slow or scored below the bar.
    Otherwise it is head, kept only if it falls in the deterministic sample.
    """
    reasons: list[str] = []
    if latency_ms >= slow_threshold_ms:
        reasons.append("slow")
    if score < score_threshold:
        reasons.append("low_score")
    if reasons:
        return SamplingDecision(keep=True, tail=True, reasons=reasons)
    if _keep_head(trace_id, base_rate):
        return SamplingDecision(keep=True, tail=False, reasons=["sampled"])
    return SamplingDecision(keep=False, tail=False, reasons=[])


def _total_latency(bundle: ReplayBundle) -> float:
    return sum(bundle.latency_ms.values()) if bundle.latency_ms else 0.0


def analyze_sampling(
    bundles: Sequence[ReplayBundle],
    *,
    base_rate: float = _DEFAULT_BASE_RATE,
    slow_threshold_ms: float = _DEFAULT_SLOW_MS,
    score_threshold: float = _DEFAULT_SCORE_THRESHOLD,
) -> TailSamplingReport:
    """Apply the tail policy to captured turns and report retention.

    Args:
        bundles: Captured turns to classify.
        base_rate: Fraction of head traces to keep.
        slow_threshold_ms: Total-latency bar above which a trace is tail.
        score_threshold: Faithfulness bar below which a trace is tail.

    Returns:
        A :class:`TailSamplingReport`. With no traces, every field is zero and
        the retention rates are ``1.0`` (nothing dropped).
    """
    n = len(bundles)
    if n == 0:
        return TailSamplingReport(
            n_traces=0,
            n_tail=0,
            n_head=0,
            n_kept=0,
            n_dropped=0,
            retention_rate=1.0,
            tail_retention_rate=1.0,
            base_rate=base_rate,
            n_slow=0,
            n_low_score=0,
            slow_threshold_ms=slow_threshold_ms,
            score_threshold=score_threshold,
        )

    n_tail = n_kept = n_kept_tail = n_slow = n_low_score = 0
    for bundle in bundles:
        decision = decide(
            trace_id=bundle.bundle_id,
            latency_ms=_total_latency(bundle),
            score=bundle.original_score,
            base_rate=base_rate,
            slow_threshold_ms=slow_threshold_ms,
            score_threshold=score_threshold,
        )
        if "slow" in decision.reasons:
            n_slow += 1
        if "low_score" in decision.reasons:
            n_low_score += 1
        if decision.tail:
            n_tail += 1
            if decision.keep:
                n_kept_tail += 1
        if decision.keep:
            n_kept += 1

    n_head = n - n_tail
    return TailSamplingReport(
        n_traces=n,
        n_tail=n_tail,
        n_head=n_head,
        n_kept=n_kept,
        n_dropped=n - n_kept,
        retention_rate=n_kept / n,
        tail_retention_rate=1.0 if n_tail == 0 else n_kept_tail / n_tail,
        base_rate=base_rate,
        n_slow=n_slow,
        n_low_score=n_low_score,
        slow_threshold_ms=slow_threshold_ms,
        score_threshold=score_threshold,
    )

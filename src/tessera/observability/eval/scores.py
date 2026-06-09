"""Eval-as-telemetry — round-trip eval scores into the stack (ADR 0010, #5).

One score becomes three signals:

1. a structured log line ``type="tessera.eval.score"`` — the key the GCP
   log-based metric and the BigQuery sink filter on
   (``infra/terraform/observability_genai.tf``);
2. a Prometheus histogram observation — for Grafana on the on-prem profile;
3. a span attribute — so the score lives inside the trace tree too.

The effect: quality becomes a time series you can alert on, exactly like latency.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from opentelemetry import trace

from tessera.observability.logging import get_logger
from tessera.observability.metrics import EVAL_SCORE

if TYPE_CHECKING:
    from tessera.observability.eval.judge import JudgeVerdict

__all__ = ["emit_score", "purge_conversation", "recent_scores"]

_log = get_logger("tessera.eval")

# A small in-process ring buffer of the most recent scores, so the dashboard can
# show live eval-as-telemetry without standing up Prometheus/BigQuery locally.
# This is a convenience view, not the system of record (that is logs + metrics).
_RECENT: deque[dict[str, object]] = deque(maxlen=200)


def recent_scores() -> list[dict[str, object]]:
    """Return the most recent eval scores (newest last)."""
    return list(_RECENT)


def purge_conversation(conversation_id: str) -> int:
    """Drop all buffered scores for a conversation (GDPR erasure, #180).

    Returns the number of score rows removed. Erasure must reach telemetry, not
    just the system of record, so a deleted subject leaves no trace here either.
    """
    kept = [s for s in _RECENT if s.get("conversation_id") != conversation_id]
    removed = len(_RECENT) - len(kept)
    _RECENT.clear()
    _RECENT.extend(kept)
    return removed


def emit_score(
    verdict: JudgeVerdict,
    *,
    language: str,
    conversation_id: str | None = None,
    sampled: bool = False,
) -> None:
    """Emit one eval score to logs, metrics, and the active span.

    Args:
        verdict: The judge's verdict for one metric.
        language: The conversation language code (``fr``/``de``/``en``).
        conversation_id: The conversation the score belongs to, if known.
        sampled: Whether this turn was scored via sampling (vs always-on flagged).
    """
    span = trace.get_current_span()
    span_context = span.get_span_context()
    trace_id = format(span_context.trace_id, "032x") if span_context.trace_id else None

    _log.info(
        "eval.score",
        type="tessera.eval.score",
        metric=verdict.metric,
        score=verdict.score,
        language=language,
        judge_model=verdict.judge_model,
        conversation_id=conversation_id,
        trace_id=trace_id,
        sampled=sampled,
    )
    EVAL_SCORE.labels(metric=verdict.metric, language=language).observe(verdict.score)
    span.set_attribute(f"tessera.eval.{verdict.metric}", verdict.score)

    _RECENT.append(
        {
            "scored_at": datetime.now(UTC).isoformat(),
            "metric": verdict.metric,
            "score": verdict.score,
            "language": language,
            "judge_model": verdict.judge_model,
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "sampled": sampled,
        }
    )

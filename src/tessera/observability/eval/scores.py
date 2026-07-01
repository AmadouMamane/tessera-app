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

import json
from collections import deque
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from opentelemetry import trace

from tessera.observability import langfuse_scores
from tessera.observability.logging import get_logger
from tessera.observability.metrics import EVAL_SCORE

if TYPE_CHECKING:
    from pathlib import Path

    from tessera.observability.eval.judge import JudgeVerdict

__all__ = ["emit_score", "persisted_scores", "purge_conversation", "recent_scores"]

_log = get_logger("tessera.eval")

# A small in-process ring buffer of the most recent scores, so the dashboard can
# show live eval-as-telemetry without standing up Prometheus/BigQuery locally.
# This is a convenience view, not the system of record (that is logs + metrics).
_RECENT: deque[dict[str, object]] = deque(maxlen=200)
_WARMED = False


def _scores_path() -> Path:
    """Durable append-only store for scores — the event log behind as-of-T reads.

    Lives next to the guard audit log (ADR 0011). Unlike ``_RECENT`` (volatile,
    bounded), this survives restarts and lets ``/observability/*?at=`` recompute
    quality/SLO/trend as of any instant T.
    """
    from tessera.settings import get_settings

    return get_settings().guard.audit_file.parent / "scores.jsonl"


def _persist(row: dict[str, object]) -> None:
    """Append one score to the durable store (best effort; never blocks a turn)."""
    try:
        path = _scores_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row) + "\n")
    except OSError:
        pass


def _warm_recent() -> None:
    """Seed the empty live buffer from the durable store after a restart.

    Mirrors the replay buffer's warm: without it, a fresh process shows no
    score-backed signals (SLO, trend, funnel…) until new traffic arrives. We load
    the most recent ``maxlen`` rows so "live" and "as of now" agree immediately.
    """
    global _WARMED
    if _WARMED or _RECENT:
        _WARMED = True
        return
    _WARMED = True
    for row in persisted_scores()[-(_RECENT.maxlen or 200) :]:
        _RECENT.append(row)


def _by_agent(rows: list[dict[str, object]], agent_id: str | None) -> list[dict[str, object]]:
    """Keep only ``agent_id``'s scores when scoped; all rows otherwise.

    A row whose ``agent_id`` is absent (pre-tagging history that could not be
    attributed) is org-only: it never belongs to a single agent's slice, so an
    agent-scoped read honestly excludes it rather than guessing.
    """
    if agent_id is None:
        return rows
    return [r for r in rows if r.get("agent_id") == agent_id]


def recent_scores(agent_id: str | None = None) -> list[dict[str, object]]:
    """Return the most recent eval scores (newest last), optionally one agent's."""
    _warm_recent()
    return _by_agent(list(_RECENT), agent_id)


def persisted_scores(at: str | None = None, agent_id: str | None = None) -> list[dict[str, object]]:
    """All durably-stored scores, optionally as of instant T and/or one agent.

    Returns rows oldest→newest; when ``at`` is set, only those with
    ``scored_at <= at`` — the as-of-T read for the cockpit time rail (ADR 0011);
    when ``agent_id`` is set, only that agent's scores (ADR 0007 attribution).
    """
    cutoff: datetime | None = None
    if at:
        try:
            cutoff = datetime.fromisoformat(at)
        except ValueError:
            cutoff = None
    rows: list[dict[str, object]] = []
    try:
        path = _scores_path()
        if not path.exists():
            return rows
        with path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    obj = json.loads(stripped)
                except ValueError:
                    continue
                if cutoff is not None:
                    try:
                        if datetime.fromisoformat(str(obj.get("scored_at", ""))) > cutoff:
                            continue
                    except ValueError:
                        pass
                rows.append(obj)
    except OSError:
        return _by_agent(rows, agent_id)
    return _by_agent(rows, agent_id)


def purge_conversation(conversation_id: str) -> int:
    """Drop all buffered scores for a conversation (GDPR erasure, #180).

    Returns the number of score rows removed. Erasure must reach telemetry, not
    just the system of record, so a deleted subject leaves no trace here either.
    """
    kept = [s for s in _RECENT if s.get("conversation_id") != conversation_id]
    removed = len(_RECENT) - len(kept)
    _RECENT.clear()
    _RECENT.extend(kept)
    # Erasure must reach the durable event log too (ADR 0011, #180).
    try:
        path = _scores_path()
        if path.exists():
            surviving = [
                row for row in persisted_scores() if row.get("conversation_id") != conversation_id
            ]
            with path.open("w", encoding="utf-8") as fp:
                for row in surviving:
                    fp.write(json.dumps(row) + "\n")
    except OSError:
        pass
    return removed


def emit_score(
    verdict: JudgeVerdict,
    *,
    language: str,
    conversation_id: str | None = None,
    sampled: bool = False,
    agent_id: str | None = None,
    model: str | None = None,
) -> None:
    """Emit one eval score to logs, metrics, the active span, and Langfuse.

    Args:
        verdict: The judge's verdict for one metric.
        language: The conversation language code (``fr``/``de``/``en``).
        conversation_id: The conversation the score belongs to, if known.
        sampled: Whether this turn was scored via sampling (vs always-on flagged).
        agent_id: The agent that produced the turn, if known — attributes the
            score so per-agent SLO / trend / funnel read the agent's own quality
            (the ``agent_id`` Prometheus label has the matching dimension).
        model: The agent's serving model for the turn (NOT the judge model) — the
            ``model`` dimension (ADR 0015 §Migration B), so quality can be sliced by
            the model that produced the answer.
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
    EVAL_SCORE.labels(
        metric=verdict.metric,
        language=language,
        agent_id=agent_id or "none",
        model=model or "unknown",
    ).observe(verdict.score)
    span.set_attribute(f"tessera.eval.{verdict.metric}", verdict.score)
    if agent_id:
        span.set_attribute("tessera.agent_id", agent_id)
    if model:
        span.set_attribute("tessera.model", model)

    row: dict[str, object] = {
        "scored_at": datetime.now(UTC).isoformat(),
        "metric": verdict.metric,
        "score": verdict.score,
        "language": language,
        "judge_model": verdict.judge_model,
        "conversation_id": conversation_id,
        "trace_id": trace_id,
        "sampled": sampled,
        "agent_id": agent_id,
        "model": model,
    }
    _RECENT.append(row)
    _persist(row)  # durable event log for as-of-T reads (ADR 0011)

    # Best-effort: mirror the verdict as a Langfuse score on the turn's trace, so eval
    # scores are queryable per-trace in Langfuse (ADR 0015 §Migration B). Never blocks or
    # raises into the turn — a slow/absent spine degrades silently, never fabricates.
    langfuse_scores.emit_langfuse_score(
        trace_id=trace_id,
        name=verdict.metric,
        value=verdict.score,
        agent_id=agent_id,
        language=language,
        model=model,
        comment=verdict.judge_model,
    )

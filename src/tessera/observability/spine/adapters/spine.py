"""The spine-backed ``SpineReader`` (ADR 0015 §Migration C).

Implements the read seam over the live spine: eval scores + captured turns from **Langfuse**
(detail), the tamper-evident **ledger** locally (the carve-out — it never leaves the process).
Aggregate *numbers* (SLO/rate/quantile) are read from **Prometheus** by the aggregate helpers,
never by summing the rows here — the hot path keeps aggregates on Prometheus, detail on
Langfuse, and never mixes the two for the same number.

This reader is not the default: it is selected via ``TESSERA_SPINE_SOURCE=spine`` or run behind
the :class:`~tessera.observability.spine.adapters.shadow.ShadowReader` (``=shadow``) which serves
jsonl and logs divergence until a signal holds parity. Until the spine has accumulated
dimensioned history, the row-level reads here are intentionally sparse — served only in shadow,
never presented as the real per-agent view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability.replay import ReplayBundle
from tessera.observability.spine.adapters.current import _read_audit_ledger
from tessera.observability.spine.adapters.langfuse import LangfuseAdapter
from tessera.observability.spine.adapters.prometheus import PrometheusAdapter

if TYPE_CHECKING:
    from tessera.observability.spine.scope import Scope

__all__ = ["SpineStoresReader"]


def _meta(row: dict[str, object]) -> dict[str, object]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


class SpineStoresReader:
    """Reads dimensioned facts from the live spine (Langfuse detail + local ledger)."""

    def __init__(
        self,
        *,
        langfuse: LangfuseAdapter | None = None,
        prometheus: PrometheusAdapter | None = None,
    ) -> None:
        self._langfuse = langfuse if langfuse is not None else LangfuseAdapter()
        self._prometheus = prometheus if prometheus is not None else PrometheusAdapter()

    @property
    def prometheus(self) -> PrometheusAdapter:
        """The Prometheus adapter (aggregate reads: SLO/rate/quantile recording rules)."""
        return self._prometheus

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Eval score rows from Langfuse scores, shaped like the jsonl store's rows."""
        rows: list[dict[str, object]] = []
        for row in self._langfuse.scores_by_metadata(scope):
            metadata = _meta(row)
            rows.append(
                {
                    "scored_at": _opt_str(row.get("timestamp")),
                    "metric": _opt_str(row.get("name")),
                    "score": row.get("value"),
                    "language": metadata.get("language"),
                    "agent_id": metadata.get("agent_id"),
                    "model": metadata.get("model"),
                    "trace_id": _opt_str(row.get("traceId")),
                    "judge_model": _opt_str(row.get("comment")),
                }
            )
        return rows

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Captured turns from Langfuse traces (best-effort; content-capture gated fields empty).

        A trace carries input/output/metadata but not the full grounding context or lineage
        (PII-gated content capture), so the mapped bundle is intentionally lossy — served only
        in shadow, never as the real bundle-derived signal until the trace payload is complete.
        """
        bundles: list[ReplayBundle] = []
        for trace in self._langfuse.traces(scope):
            metadata = _meta(trace)
            bundles.append(
                ReplayBundle(
                    bundle_id=str(trace.get("id", "")),
                    captured_at=str(trace.get("timestamp", "")),
                    conversation_id=_opt_str(trace.get("sessionId")),
                    language=str(metadata.get("language") or ""),
                    question=str(trace.get("input") or ""),
                    context="",
                    original_answer=str(trace.get("output") or ""),
                    original_model=str(metadata.get("model") or ""),
                    original_score=0.0,
                    lineage=None,
                    latency_ms=None,
                    agent_id=_opt_str(metadata.get("agent_id")),
                )
            )
        return bundles

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:  # noqa: ARG002
        """The tamper-evident ledger — always local (the ADR carve-out), never in Langfuse."""
        return _read_audit_ledger()

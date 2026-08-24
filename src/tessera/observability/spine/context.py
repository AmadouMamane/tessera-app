"""Per-snapshot shared-read context — the anti-fan-out (ADR 0015 §Performance 2).

One snapshot loads each underlying store **at most once**; every signal derives from the
shared reads. Implemented as a :mod:`contextvars` variable so signal reads keep a clean
``(Scope)`` signature yet transparently share reads when run inside a snapshot. Outside a
snapshot a signal read creates its own one-shot context, so it still works standalone.
"""

from __future__ import annotations

import contextvars
from functools import cache
from typing import TYPE_CHECKING

from tessera.observability.spine.adapters import SpineReader, get_reader

if TYPE_CHECKING:
    from tessera.observability.replay import ReplayBundle
    from tessera.observability.spine.scope import Scope

__all__ = [
    "SnapshotContext",
    "bind_context",
    "current_context",
    "reset_context",
]


class SnapshotContext:
    """Memoises the four shared reads (scores / bundles / audit / gating) for one snapshot.

    ``upstream_reads`` counts distinct backend loads — the metric the perf probe asserts
    stays O(1) (a small constant), proving the snapshot shares reads instead of fanning out
    one read per signal.
    """

    def __init__(self, reader: SpineReader | None = None) -> None:
        self._reader = reader if reader is not None else get_reader()
        self._scores: dict[str, list[dict[str, object]]] = {}
        self._bundles: dict[str, list[ReplayBundle]] = {}
        self._audit: list[dict[str, object]] | None = None
        self._gating: dict[str, list[dict[str, object]]] = {}
        self.upstream_reads = 0

    def scores(self, scope: Scope) -> list[dict[str, object]]:
        """Scores for the scope, read from the backend at most once per snapshot.

        The judge's plane is kept to the agents that DECLARE it here, at the one
        seam every score-backed signal reads through — whichever adapter serves
        the rows (see :func:`_declared_judged_rows`).
        """
        cache_key = scope.key()
        cached = self._scores.get(cache_key)
        if cached is None:
            self.upstream_reads += 1
            cached = _declared_judged_rows(self._reader.scores(scope))
            self._scores[cache_key] = cached
        return cached

    def bundles(self, scope: Scope) -> list[ReplayBundle]:
        """Bundles for the scope, read from the backend at most once per snapshot."""
        cache_key = scope.key()
        cached = self._bundles.get(cache_key)
        if cached is None:
            self.upstream_reads += 1
            cached = self._reader.bundles(scope)
            self._bundles[cache_key] = cached
        return cached

    def audit_entries(self, scope: Scope) -> list[dict[str, object]]:
        """The ledger, read whole exactly once per snapshot (signals filter downstream)."""
        # The ledger is read whole (unfiltered) once; signals apply the scope filter
        # downstream, so one read serves every audit-derived signal in the snapshot.
        if self._audit is None:
            self.upstream_reads += 1
            self._audit = self._reader.audit_entries(scope)
        return self._audit

    def gating_scores(self, scope: Scope) -> list[dict[str, object]]:
        """Gating rows for the scope, read from the backend at most once per snapshot."""
        cache_key = scope.key()
        cached = self._gating.get(cache_key)
        if cached is None:
            self.upstream_reads += 1
            cached = self._reader.gating_scores(scope)
            self._gating[cache_key] = cached
        return cached


_current: contextvars.ContextVar[SnapshotContext | None] = contextvars.ContextVar(
    "tessera_snapshot_context", default=None
)


def current_context() -> SnapshotContext:
    """The bound snapshot context, or a fresh one-shot context for a standalone read."""
    ctx = _current.get()
    return ctx if ctx is not None else SnapshotContext()


def bind_context(ctx: SnapshotContext) -> contextvars.Token[SnapshotContext | None]:
    """Bind ``ctx`` as the ambient context for the duration of a snapshot compute."""
    return _current.set(ctx)


def reset_context(token: contextvars.Token[SnapshotContext | None]) -> None:
    """Unbind the snapshot context (pair with :func:`bind_context`)."""
    _current.reset(token)


@cache
def _non_judged_agent_ids() -> frozenset[str]:
    """Registry agents whose DECLARED quality regime is not ``llm_judged``.

    Read once per process through the one projector (the registry is static for a
    process's lifetime). Only an explicit non-judged declaration excludes an id —
    an agent the projector cannot describe stays in the judged plane, the same
    unknown-keeps-today's-behaviour rule the write-side guard applies.
    """
    from tessera.agent.registry import QualityRegime, list_agents
    from tessera.observability.agentspec_projection import quality_regime_descriptor

    excluded: set[str] = set()
    for agent in list_agents():
        descriptor = quality_regime_descriptor(agent)
        if descriptor is not None and descriptor["regime"] != QualityRegime.LLM_JUDGED.value:
            excluded.add(agent.id)
    return frozenset(excluded)


def _declared_judged_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep the judge's plane to the agents that DECLARE it (ADR 0017 §A4, ADR 0053 §4).

    A score row attributed to an agent whose declared regime is not ``llm_judged``
    never enters a score-backed signal: the judged population is a declaration,
    not an accident of routing. Measured leak, 2026-08-22 — one operator-side
    /chat turn routed to recouvrement was judged, and that single row became the
    whole per-agent SLO population ("100,0 %" on n=1). Nothing is destroyed: the
    durable log keeps every row; the plane the surfaces read simply excludes them.
    Rows with no ``agent_id`` (pre-tagging history) and rows naming an id the
    registry does not know are kept — the filter narrows by declaration only.
    """
    excluded = _non_judged_agent_ids()
    if not excluded:
        return rows
    return [row for row in rows if str(row.get("agent_id") or "") not in excluded]

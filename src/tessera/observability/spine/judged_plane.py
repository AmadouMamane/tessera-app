"""The judged plane is DECLARED (ADR 0017 §A4, ADR 0053 §4) — one filter, every door.

A score row attributed to an agent whose declared quality regime is not ``llm_judged``
never enters a score-backed signal: the judged population is a declaration, not an
accident of routing. Measured leak, 2026-08-22 — one operator-side /chat turn routed to
recouvrement was judged, and that single row became the whole per-agent SLO population
("100,0 %" rendered on n=1). Nothing is destroyed: the durable log keeps every row; the
plane the surfaces read simply excludes them.

Two read doors exist at the same level — :meth:`SnapshotContext.scores` (the snapshot's
memoised read) and :func:`read_scores` (the routes' direct seam) — and the parity ratchet
(`test_spine_signals_parity`) rightly refuses a filter that covers only one of them. Both
doors call :func:`declared_judged_rows`; the fake reader stays raw so tests seed exactly
what they mean to.
"""

from __future__ import annotations

from functools import cache


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


def declared_judged_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep the judged plane to the agents that DECLARE it.

    Rows with no ``agent_id`` (pre-tagging history) and rows naming an id the
    registry does not know are kept — the filter narrows by declaration only.
    """
    excluded = _non_judged_agent_ids()
    if not excluded:
        return rows
    return [row for row in rows if str(row.get("agent_id") or "") not in excluded]

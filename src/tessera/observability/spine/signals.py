"""Signal read implementations for the batched snapshot (ADR 0015 §Migration A).

Each read mirrors its existing route body exactly, but sources its store reads from the
shared :class:`~tessera.observability.spine.context.SnapshotContext` so a snapshot loads
scores / bundles / the ledger **once** and every signal derives from them (the anti-fan-out).
Parity with the routes is asserted in ``tests/unit/test_spine_signals_parity.py``.

Only the store-derived, scope-varying signals are registered here (the hot path). Org-wide
fixed-corpus probes and deterministic fixtures are *declared* in :mod:`capabilities` (so the
UI can badge them) but keep their own cached endpoints — they do not vary with agent/time.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from tessera.observability import (
    anomalies as anomalies_mod,
    business_capabilities as business_capabilities_mod,
    business_events as business_events_mod,
    business_scoring as business_scoring_mod,
    conformance as conformance_mod,
    cost_anomaly as cost_anomaly_mod,
    funnel as funnel_mod,
    governance_feed as governance_feed_mod,
    pii_leak as pii_leak_mod,
    slo as slo_mod,
    tool_validity as tool_validity_mod,
    toxicity as toxicity_mod,
    trends as trends_mod,
    whatchanged as whatchanged_mod,
)
from tessera.observability.spine.adapters import ledger
from tessera.observability.spine.context import current_context

if TYPE_CHECKING:
    from tessera.observability.spine.registry import SignalRegistry
    from tessera.observability.spine.scope import Scope

__all__ = ["register_all"]

_MIN_LINEAGE_TURNS = 2  # need two lineage-bearing turns to diff (mirrors the route)


def _faithfulness(scores: list[dict[str, object]]) -> list[float]:
    return [
        float(s["score"])  # type: ignore[arg-type]
        for s in scores
        if s.get("metric") == "faithfulness"
    ]


async def _read_scores(scope: Scope) -> dict[str, object]:
    return {
        "scores": current_context().scores(scope),
        "as_of": scope.at,
        "agent": scope.agent_param,
        # Echoes the window that was actually applied. The snapshot slice carries a scope
        # report and could do without it; the standalone route has no report, so a direct
        # caller has no other way to tell "7 days" from "everything" — and parity requires
        # the two to say the same thing.
        "days": scope.period_days,
    }


async def _read_slo(scope: Scope) -> dict[str, object]:
    # The same one derivation the standalone route calls (`slo_payload`): headline +
    # per-language slices, so the snapshot slice and the route stay byte-identical by
    # construction (test_spine_signals_parity witnesses it).
    return {
        **slo_mod.slo_payload(current_context().scores(scope)),
        "as_of": scope.at,
        "agent": scope.agent_param,
    }


async def _read_trend(scope: Scope) -> dict[str, object]:
    points: list[tuple[str, float]] = []
    for s in current_context().scores(scope):
        if s.get("metric") != "faithfulness":
            continue
        scored_at = s.get("scored_at")
        points.append(
            (scored_at if isinstance(scored_at, str) else "", float(s["score"]))  # type: ignore[arg-type]
        )
    return {
        **asdict(trends_mod.analyze_trend(points)),
        "as_of": scope.at,
        "agent": scope.agent_param,
    }


async def _read_funnel(scope: Scope) -> dict[str, object]:
    turns: list[tuple[str, str | None, float]] = []
    for s in current_context().scores(scope):
        lang = s.get("language")
        conv = s.get("conversation_id")
        raw = s.get("score", 0.0)
        turns.append(
            (
                lang if isinstance(lang, str) else "unknown",
                conv if isinstance(conv, str) else None,
                float(raw),  # type: ignore[arg-type]
            )
        )
    return asdict(funnel_mod.aggregate_funnel(turns))


async def _read_gating(scope: Scope) -> dict[str, object]:
    """Compact release-gating summary from the porteur rows (§Amendment 2).

    The rows themselves are bounded but verbose (cases x languages x runs), so the
    snapshot carries per-run aggregates + the latest run's verdict — enough for a
    release card without dumping the socle into every payload.
    """
    rows = current_context().gating_scores(scope)
    runs: dict[str, dict[str, object]] = {}
    for row in rows:
        run_id = str(row.get("run_id") or "")
        run = runs.setdefault(
            run_id,
            {"run_id": run_id, "agent_id": row.get("agent_id"), "passed": 0, "total": 0, "at": ""},
        )
        run["total"] = int(run["total"]) + 1  # type: ignore[call-overload]
        if row.get("passed"):
            run["passed"] = int(run["passed"]) + 1  # type: ignore[call-overload]
        scored_at = str(row.get("scored_at") or "")
        if scored_at > str(run["at"]):
            run["at"] = scored_at
    latest = max(runs.values(), key=lambda r: str(r["at"])) if runs else None
    return {
        "row_count": len(rows),
        "run_count": len(runs),
        "latest_run": latest,
        "as_of": scope.at,
        "agent": scope.agent_param,
    }


async def _read_toxicity(scope: Scope) -> dict[str, object]:
    turns = [(b.question, b.original_answer) for b in current_context().bundles(scope)]
    return asdict(toxicity_mod.scan_toxicity(turns))


async def _read_pii_leak(scope: Scope) -> dict[str, object]:
    turns = [
        (b.original_answer, f"{b.question}\n{b.context}") for b in current_context().bundles(scope)
    ]
    return asdict(pii_leak_mod.aggregate_leaks(turns))


async def _read_cost(scope: Scope) -> dict[str, object]:
    turns = [
        (b.question, f"{b.question}\n{b.context}\n{b.original_answer}")
        for b in current_context().bundles(scope)
    ]
    return asdict(cost_anomaly_mod.analyze_costs(turns))


async def _read_anomalies(scope: Scope) -> dict[str, object]:
    by_conversation: dict[str, list[str]] = {}
    for bundle in current_context().bundles(scope):
        key = bundle.conversation_id or "<none>"
        by_conversation.setdefault(key, []).append(bundle.question)
    return asdict(anomalies_mod.detect_anomalies(by_conversation))


async def _read_what_changed(scope: Scope) -> dict[str, object]:
    with_lineage = [b for b in current_context().bundles(scope) if b.lineage is not None]
    if len(with_lineage) < _MIN_LINEAGE_TURNS:
        return {"available": False}
    prev, curr = with_lineage[-2], with_lineage[-1]
    assert prev.lineage is not None  # narrowed by the filter above
    assert curr.lineage is not None
    report = whatchanged_mod.what_changed(
        prev_lineage=prev.lineage,
        prev_score=prev.original_score,
        curr_lineage=curr.lineage,
        curr_score=curr.original_score,
    )
    return {"available": True, **asdict(report)}


async def _read_conformance(scope: Scope) -> dict[str, object]:
    return asdict(
        conformance_mod.compute_conformance(
            at=scope.at, agent_id=scope.agent_id, days=scope.period_days
        )
    )


async def _read_tool_validity(scope: Scope) -> dict[str, object]:
    return asdict(
        tool_validity_mod.compute_tool_validity(
            at=scope.at, agent_id=scope.agent_id, days=scope.period_days
        )
    )


async def _read_governance(scope: Scope) -> dict[str, object]:
    feed = governance_feed_mod.compute_governance_feed(scope.at, limit=8, agent=scope.agent_param)
    return {"available": True, **asdict(feed)}


async def _read_business_events(scope: Scope) -> dict[str, object]:
    rows = business_events_mod.business_event_rows(at=scope.at, agent_id=scope.agent_id)
    return {
        "events": rows,
        "as_of": scope.at,
        "agent": scope.agent_param,
    }


async def _read_recouvrement_business_scores(scope: Scope) -> dict[str, object]:
    rows = business_events_mod.business_event_rows(at=scope.at, agent_id=scope.agent_id)
    return {
        "scores": business_scoring_mod.score_rows(rows),
        "as_of": scope.at,
        "agent": scope.agent_param,
    }


async def _read_business_capabilities(scope: Scope) -> dict[str, object]:
    # One source with GET /observability/business/capabilities: the same aggregate over the
    # same fact, narrowed to the snapshot's agent+time dims (the finer route filters default
    # to None, matching a page-load read). Parity is asserted in test_spine_signals_parity.
    return business_capabilities_mod.business_capability_aggregate(
        at=scope.at, agent_id=scope.agent_id
    )


async def _read_audit_count(scope: Scope) -> dict[str, object]:
    # A live read needs only the COUNT: ask the database for it (one aggregate row) instead
    # of materialising 94 % of the chain to take its length — six times per fleet snapshot.
    # `count_for_scope` returns None for an as-of read or the flat-file source, where the
    # Python materialise+filter preserves `occurred_before`'s fail-open semantics exactly.
    count = ledger.count_for_scope(scope)
    if count is None:
        count = len(ledger.events_for_scope(current_context().audit_entries(scope), scope))
    return {"entry_count": count, "as_of": scope.at, "agent": scope.agent_param}


async def _read_audit_integrity(_scope: Scope) -> dict[str, object]:
    """Org-wide crypto invariant: the whole hash chain (all entry types), never per-agent.

    Verifies the full ACTIVE ledger (§Amendment 3: the flat file by default, the promoted
    append-only Postgres table after the cut) — a per-agent sub-chain would be a weaker
    guarantee, so this intentionally bypasses the scope-filtered ctx entries. The scope is
    unused: integrity is a whole-fleet property (its capability declares no dims).
    """
    from tessera.guard.ledger_store import active_ledger_tree_status, ledger_source

    tree = active_ledger_tree_status()
    return {
        # TESS-LEDGER-001 — content integrity (tamper-evidence) is distinct from total order.
        # ``chain_valid`` now tracks content integrity so a historical fork does not read as
        # tampering; ``linear``/``forks`` carry the total-order nuance for the badge + evidence.
        "chain_valid": tree.content_integrity,
        "content_integrity": tree.content_integrity,
        "linear": tree.linear,
        "fork_count": tree.fork_count,
        "forks": [{"prev_hash": f.prev_hash, "children": list(f.children)} for f in tree.forks],
        "orphan_count": tree.orphan_count,
        "orphans": list(tree.orphans),
        "attested": tree.attested,
        "length": tree.length,
        "broken_at": tree.broken_at,
        "medium": ledger_source(),
    }


_READS = {
    "scores": _read_scores,
    "slo": _read_slo,
    "trend": _read_trend,
    "funnel": _read_funnel,
    "gating": _read_gating,
    "toxicity": _read_toxicity,
    "pii_leak": _read_pii_leak,
    "cost": _read_cost,
    "anomalies": _read_anomalies,
    "what_changed": _read_what_changed,
    "conformance": _read_conformance,
    "tool_validity": _read_tool_validity,
    "governance": _read_governance,
    "business_events": _read_business_events,
    "recouvrement_business_scores": _read_recouvrement_business_scores,
    "business_capabilities": _read_business_capabilities,
    "audit_count": _read_audit_count,
    "audit_integrity": _read_audit_integrity,
}


def register_all(registry: SignalRegistry) -> None:
    """Register every store-derived hot-path signal with the registry."""
    for signal_id, read in _READS.items():
        registry.register(signal_id, read)

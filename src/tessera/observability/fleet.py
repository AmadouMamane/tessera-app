"""Fleet rollup — per-agent health/volume + conversation-level dedup (Phase 3).

The fleet view and the agent switcher read this. It combines the registry (so
all agents appear, with their names/owners, even with no traffic), the durable
transcript (volume + observable escalation rate + per-agent latency) and the S1
journal (handoffs in/out). Org totals count a conversation **once** even when it
spans two agents — never the naive per-agent sum.

Observable KPIs (volume, escalation rate, latency, handoffs) are real and differ
per agent. Judged quality (resolution/faithfulness) stays shared until per-agent
eval (Phase 4) and is intentionally absent here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row

from tessera.guard.ledger_store import read_ledger_entries
from tessera.observability.agent_release import fleet_release_states
from tessera.observability.agent_scope import dedup_org_total
from tessera.observability.agentspec_projection import observability_level
from tessera.observability.business_capabilities import business_capability_aggregate
from tessera.observability.operator_items import load_items
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

    from tessera.agent.registry import Agent

__all__ = ["compute_fleet"]

_ESCALATION_ILIKE = (
    "content ILIKE '%%escalad%%' OR content ILIKE '%%conseiller%%' "
    "OR content ILIKE '%%ticket%%' OR content ILIKE '%%transf%%'"
)
_GOOD_ESCALATION = 20.0  # % escalated turns under which an agent reads "healthy"
_WARN_ESCALATION = 35.0


def _registry_agents() -> list[dict[str, str]]:
    try:
        from tessera.agent.registry import list_agents

        return [
            {"id": a.id, "name": a.name, "owner": a.owner, "audience": a.audience.value}
            for a in list_agents()
        ]
    except (OSError, ValueError):
        return []


def _agent_records() -> dict[str, Agent]:
    """Full agent records, for manifest-derived fields (the level badge).

    Empty on a load error — the fleet then degrades to no level badge, never crashes.
    """
    try:
        from tessera.agent.registry import list_agents

        return {a.id: a for a in list_agents()}
    except (OSError, ValueError):
        return {}


def _handoff_counts(audit_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Count S1 handoff events per agent: (incoming by to_agent, outgoing by from_agent)."""
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    for obj in read_ledger_entries(audit_path):
        if obj.get("type") != "tessera.agent.handoff":
            continue
        to_agent = str(obj.get("to_agent", ""))
        from_agent = str(obj.get("from_agent", ""))
        if to_agent:
            incoming[to_agent] = incoming.get(to_agent, 0) + 1
        if from_agent:
            outgoing[from_agent] = outgoing.get(from_agent, 0) + 1
    return incoming, outgoing


def _health(escalation_rate: float) -> str:
    if escalation_rate <= _GOOD_ESCALATION:
        return "good"
    if escalation_rate <= _WARN_ESCALATION:
        return "warn"
    return "crit"


def _business_card_facts(aid: str, record: Agent | None) -> dict[str, object]:
    """Manifest-derived business chip + pending operator items for one fleet card."""
    if record is None or record.observability is None:
        return {"north_star": None, "pending_business_items": 0}
    try:
        aggregate = business_capability_aggregate(agent_id=aid)
    except Exception:
        aggregate = {}
    raw_signals = aggregate.get("business_signals")
    signals = raw_signals if isinstance(raw_signals, list) else []
    north_star = next(
        (
            signal
            for signal in signals
            if isinstance(signal, dict) and signal.get("north_star") is True
        ),
        None,
    )
    try:
        pending = sum(
            1
            for item in load_items(aid)
            if item.source_kind == "business_event" and item.status != "done"
        )
    except Exception:
        pending = 0
    return {"north_star": north_star, "pending_business_items": pending}


async def compute_fleet(lang: str = "fr") -> dict[str, object]:
    """Return the fleet payload: per-agent observable KPIs + deduplicated org totals.

    ``lang`` localizes the per-agent release ``verdict_label``; all other fields
    are language-independent.
    """
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT agent_id, "  # noqa: S608  (escalation clause is a constant)
                "count(DISTINCT conversation_id) AS convs, "
                "count(*) FILTER (WHERE role = 'user') AS turns, "
                "count(*) AS msgs, "
                f"count(*) FILTER (WHERE role = 'assistant' AND ({_ESCALATION_ILIKE})) AS escal, "
                "count(*) FILTER (WHERE role = 'assistant') AS answers, "
                "avg(latency_ms) FILTER (WHERE latency_ms IS NOT NULL) AS lat "
                "FROM conversation_messages GROUP BY agent_id"
            )
            by_agent = {str(r["agent_id"]): r for r in await cur.fetchall()}

            await cur.execute(
                "SELECT count(*) FILTER (WHERE role = 'user') AS turns FROM conversation_messages"
            )
            org_turns = int((await cur.fetchone() or {}).get("turns") or 0)

            # Deduplicated conversation rollup via the shared helper — a handoff
            # conversation counts ONCE for the org, never the per-agent sum.
            rollup = await dedup_org_total(
                cur, table="conversation_messages", entity_col="conversation_id"
            )

    incoming, outgoing = _handoff_counts(get_settings().guard.audit_file)
    releases = fleet_release_states(lang)
    records = _agent_records()

    # Registry first (every agent appears), enriched with its real slice.
    agents: list[dict[str, Any]] = []
    for reg in _registry_agents():
        aid = reg["id"]
        row = by_agent.get(aid, {})
        answers = int(row.get("answers") or 0)
        escal = int(row.get("escal") or 0)
        escalation_rate = round(100 * escal / answers, 1) if answers else 0.0
        lat = row.get("lat")
        rel = releases.get(aid)
        record = records.get(aid)
        # L2 (Governed) requires the eval/guard facts to be VISIBLE — a real gating socle
        # actually ran (ADR 0017 §4). The level is computed from this fact, never asserted.
        governed = rel is not None and rel.available and rel.socle_total > 0
        level = observability_level(record, governed=governed) if record is not None else None
        business_facts = _business_card_facts(aid, record)
        agents.append(
            {
                "id": aid,
                "name": reg["name"],
                "owner": reg["owner"],
                "audience": reg.get("audience", "operator"),
                "conversations": int(row.get("convs") or 0),
                "turns": int(row.get("turns") or 0),
                "messages": int(row.get("msgs") or 0),
                "escalation_rate": escalation_rate,
                "latency_ms": round(float(lat), 1) if lat is not None else None,
                "handoffs_in": int(incoming.get(aid, 0)),
                "handoffs_out": int(outgoing.get(aid, 0)),
                "health": _health(escalation_rate),
                "release": rel.as_dict() if rel else None,
                # ADR 0017 §4 — observability level (L0-L2 in Phase B; None when the agent
                # has no AgentSpec manifest yet → honest-empty, not "L0").
                "level": level,
                **business_facts,
            }
        )

    return {
        "agents": agents,
        "org": {"conversations": rollup.org, "turns": org_turns},
        "naive_sum_conversations": rollup.naive_sum,
        "shared_conversations": rollup.shared,
        "dedup_saved": rollup.dedup_saved,
    }

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
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

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
            }
        )

    return {
        "agents": agents,
        "org": {"conversations": rollup.org, "turns": org_turns},
        "naive_sum_conversations": rollup.naive_sum,
        "shared_conversations": rollup.shared,
        "dedup_saved": rollup.dedup_saved,
    }

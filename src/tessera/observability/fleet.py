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

import json
from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row

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

        return [{"id": a.id, "name": a.name, "owner": a.owner} for a in list_agents()]
    except (OSError, ValueError):
        return []


def _handoff_counts(audit_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Count S1 handoff events per agent: (incoming by to_agent, outgoing by from_agent)."""
    incoming: dict[str, int] = {}
    outgoing: dict[str, int] = {}
    if not audit_path.exists():
        return incoming, outgoing
    with audit_path.open("r", encoding="utf-8") as fp:
        for raw in fp:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
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


async def compute_fleet() -> dict[str, object]:
    """Return the fleet payload: per-agent observable KPIs + deduplicated org totals."""
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
                "SELECT count(DISTINCT conversation_id) AS convs, "
                "count(*) FILTER (WHERE role = 'user') AS turns FROM conversation_messages"
            )
            org = await cur.fetchone() or {}

            await cur.execute(
                "SELECT count(*) AS n FROM ("
                "  SELECT conversation_id FROM conversation_messages "
                "  GROUP BY conversation_id HAVING count(DISTINCT agent_id) > 1"
                ") s"
            )
            shared = (await cur.fetchone() or {}).get("n", 0)

    incoming, outgoing = _handoff_counts(get_settings().guard.audit_file)

    # Registry first (every agent appears), enriched with its real slice.
    agents: list[dict[str, Any]] = []
    naive_sum = 0
    for reg in _registry_agents():
        aid = reg["id"]
        row = by_agent.get(aid, {})
        convs = int(row.get("convs") or 0)
        answers = int(row.get("answers") or 0)
        escal = int(row.get("escal") or 0)
        escalation_rate = round(100 * escal / answers, 1) if answers else 0.0
        lat = row.get("lat")
        naive_sum += convs
        agents.append(
            {
                "id": aid,
                "name": reg["name"],
                "owner": reg["owner"],
                "conversations": convs,
                "turns": int(row.get("turns") or 0),
                "messages": int(row.get("msgs") or 0),
                "escalation_rate": escalation_rate,
                "latency_ms": round(float(lat), 1) if lat is not None else None,
                "handoffs_in": int(incoming.get(aid, 0)),
                "handoffs_out": int(outgoing.get(aid, 0)),
                "health": _health(escalation_rate),
            }
        )

    org_convs = int(org.get("convs") or 0)
    return {
        "agents": agents,
        "org": {"conversations": org_convs, "turns": int(org.get("turns") or 0)},
        "naive_sum_conversations": naive_sum,
        "shared_conversations": int(shared or 0),
        "dedup_saved": naive_sum - org_convs,
    }

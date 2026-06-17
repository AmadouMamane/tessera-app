"""Cross-agent rollups with conversation-level dedup (multi-agent Phase 2/3).

Org totals must count a conversation **once**, even when it spans two agents
(a handoff). Naively summing per-agent conversation counts double-counts every
shared conversation. This module exposes both — the per-agent slices and the
deduplicated org total — so the fleet view (Phase 3) and SURVEILLER can show
honest org figures while the per-agent Synthèse keeps its own slice.

Sourced from the durable transcript; numbers are real, never summed naively.
"""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from tessera.retrieval.store import _connection

__all__ = ["compute_fleet_rollup"]


def _agent_name(agent_id: str) -> str:
    try:
        from tessera.agent.registry import get_agent

        return get_agent(agent_id).name
    except (KeyError, OSError, ValueError):
        return agent_id


async def compute_fleet_rollup() -> dict[str, object]:
    """Per-agent conversation/turn counts + the deduplicated org total.

    ``org.conversations`` counts distinct conversation ids across all agents (a
    shared conversation once); ``naive_sum_conversations`` sums the per-agent
    counts (a shared conversation twice). ``dedup_saved`` is their difference —
    the number of cross-agent conversations that a naive sum would double-count.
    """
    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT agent_id, count(DISTINCT conversation_id) AS convs, "
                "count(*) FILTER (WHERE role = 'user') AS turns "
                "FROM conversation_messages GROUP BY agent_id ORDER BY agent_id"
            )
            per_agent_rows = list(await cur.fetchall())

            await cur.execute(
                "SELECT count(DISTINCT conversation_id) AS convs, "
                "count(*) FILTER (WHERE role = 'user') AS turns "
                "FROM conversation_messages"
            )
            org = await cur.fetchone() or {}

            await cur.execute(
                "SELECT count(*) AS n FROM ("
                "  SELECT conversation_id FROM conversation_messages "
                "  GROUP BY conversation_id HAVING count(DISTINCT agent_id) > 1"
                ") s"
            )
            shared = (await cur.fetchone() or {}).get("n", 0)

    per_agent: list[dict[str, Any]] = [
        {
            "id": str(r["agent_id"]),
            "name": _agent_name(str(r["agent_id"])),
            "conversations": int(r["convs"] or 0),
            "turns": int(r["turns"] or 0),
        }
        for r in per_agent_rows
    ]
    naive_sum = sum(a["conversations"] for a in per_agent)
    org_convs = int(org.get("convs") or 0)
    return {
        "agents": per_agent,
        "org": {"conversations": org_convs, "turns": int(org.get("turns") or 0)},
        "naive_sum_conversations": naive_sum,
        "shared_conversations": int(shared or 0),
        # What a naive per-agent sum would over-count (one extra hit per shared conv).
        "dedup_saved": naive_sum - org_convs,
    }

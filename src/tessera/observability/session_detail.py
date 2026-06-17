"""Conversation session detail — turn-by-turn, with per-turn agent attribution.

The drill-down behind a conversation: each turn shows *which agent handled it*
(the multi-agent per-turn attribution), so a conversation that spans two agents
reads as a clear hand-over. Sourced from the durable transcript
(``conversation_messages``, the ``agent_id`` stamped per message) and from the S1
journal for the agent->agent **handoff** events (distinct from human escalation).

Everything is real: turns, agents and handoffs come from stored data, never
fabricated. The page is read-only.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from tessera.observability._asof import occurred_before
from tessera.retrieval.store import _connection
from tessera.settings import get_settings

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["compute_session_detail"]

_PARIS = ZoneInfo("Europe/Paris")


def _agent_name(agent_id: str) -> str:
    """Human name for an agent id, from the registry (falls back to the id)."""
    try:
        from tessera.agent.registry import get_agent

        return get_agent(agent_id).name
    except (KeyError, OSError, ValueError):
        return agent_id


def _fmt_time(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(value.astimezone(_PARIS).strftime("%d/%m/%Y %H:%M"))
    except (AttributeError, ValueError):
        return str(value)


def _read_handoffs(conversation_id: str, audit_path: Path, at: str | None) -> list[dict[str, Any]]:
    """Read agent->agent handoff events for this conversation from the S1 journal."""
    if not audit_path.exists():
        return []
    out: list[dict[str, Any]] = []
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
            if obj.get("conversation_id") != conversation_id:
                continue
            if not occurred_before(obj.get("occurred_at"), at):
                continue
            out.append(
                {
                    "from": str(obj.get("from_agent", "")),
                    "to": str(obj.get("to_agent", "")),
                    "reason": str(obj.get("reason", "")),
                    "turn_id": str(obj.get("turn_id", "")),
                }
            )
    return out


async def compute_session_detail(
    conversation_id: str, at: str | None = None
) -> dict[str, object]:
    """Return the turn-by-turn detail of one conversation, attributed per agent.

    Args:
        conversation_id: The conversation (UUID) to reconstruct.
        at: Optional as-of instant (ISO) bounding the S1 handoff events read.
    """
    try:
        conv_uuid = UUID(conversation_id)
    except (ValueError, TypeError):
        return {"available": False}

    async with _connection() as conn:
        conn.row_factory = dict_row
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT turn_id, seq, agent_id, role, content, created_at "
                "FROM conversation_messages WHERE conversation_id = %s ORDER BY id ASC",
                (conv_uuid,),
            )
            rows = list(await cur.fetchall())

    if not rows:
        return {"available": False}

    # Group rows into turns (one user + one assistant share a turn_id), preserving
    # order; each turn is credited to the agent stamped on it (per-turn attribution).
    turns: list[dict[str, Any]] = []
    by_turn: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for r in rows:
        tid = str(r["turn_id"])
        if tid not in by_turn:
            by_turn[tid] = {"agent_id": r["agent_id"], "created_at": r["created_at"]}
            order.append(tid)
        if r["role"] == "user":
            by_turn[tid]["question"] = r["content"]
        elif r["role"] == "assistant":
            by_turn[tid]["answer"] = r["content"]

    agents_seen: list[str] = []
    for i, tid in enumerate(order, start=1):
        t = by_turn[tid]
        agent_id = str(t["agent_id"])
        if agent_id not in agents_seen:
            agents_seen.append(agent_id)
        turns.append(
            {
                "turn": i,
                "agent_id": agent_id,
                "agent_name": _agent_name(agent_id),
                "question": str(t.get("question", "")),
                "answer": str(t.get("answer", "")),
                "time": _fmt_time(t.get("created_at")),
            }
        )

    handoffs = _read_handoffs(conversation_id, get_settings().guard.audit_file, at)
    first_q = next((t["question"] for t in turns if t["question"]), "Conversation")
    return {
        "available": True,
        "conversation_id": conversation_id,
        "title": first_q,
        "agents": [{"id": a, "name": _agent_name(a)} for a in agents_seen],
        "handoffs": [
            {
                "from": h["from"],
                "from_name": _agent_name(h["from"]),
                "to": h["to"],
                "to_name": _agent_name(h["to"]),
                "reason": h["reason"],
            }
            for h in handoffs
        ],
        "turns": turns,
        "stats": {"turns": len(turns), "agents": len(agents_seen)},
        "spans_agents": len(agents_seen) > 1,
    }

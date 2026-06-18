"""Unit tests for the shared multi-agent dedup helper (GOUVERNER / PLATEFORME)."""

from __future__ import annotations

import pytest

from tessera.observability.agent_scope import dedup_org_total


class _FakeCursor:
    """Minimal async cursor returning canned rows per query shape.

    Models a tiny ``(conversation_id, agent_id)`` table where conversation ``c3``
    spanned two agents (a handoff) — so the org total must dedupe it to one.
    """

    def __init__(self) -> None:
        self._last = ""
        self._rows: dict[str, object] = {}

    async def execute(self, sql: str) -> None:
        self._last = sql

    async def fetchall(self) -> list[dict[str, object]]:
        # Per-agent distinct conversation counts: a=2 (c1,c3), b=2 (c2,c3).
        return [{"agent": "a", "n": 2}, {"agent": "b", "n": 2}]

    async def fetchone(self) -> dict[str, object]:
        if "HAVING" in self._last:  # shared = conversations touching >1 agent
            return {"n": 1}
        return {"n": 3}  # distinct org conversations: c1, c2, c3


@pytest.mark.asyncio
async def test_dedup_org_total_dedupes_handoff_conversation() -> None:
    rollup = await dedup_org_total(
        _FakeCursor(),  # type: ignore[arg-type]
        table="conversation_messages",
        entity_col="conversation_id",
    )
    assert rollup.by_agent == {"a": 2, "b": 2}
    assert rollup.naive_sum == 4  # the misleading sum
    assert rollup.org == 3  # the deduped truth
    assert rollup.shared == 1  # c3 spanned two agents
    assert rollup.dedup_saved == 1  # 4 - 3


@pytest.mark.asyncio
async def test_dedup_org_total_rejects_unsafe_identifiers() -> None:
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        await dedup_org_total(
            _FakeCursor(),  # type: ignore[arg-type]
            table="conversation_messages; DROP TABLE x",
            entity_col="conversation_id",
        )
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        await dedup_org_total(
            _FakeCursor(),  # type: ignore[arg-type]
            table="conversation_messages",
            entity_col="conversation_id) FROM t --",
        )

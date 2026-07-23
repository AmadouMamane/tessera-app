"""Unit tests for the shared multi-agent dedup helper (GOUVERNER / PLATEFORME)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tessera.observability.agent_scope import dedup_org_total, shared_entities_among


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


class _RecordingCursor:
    """Records every executed SQL string, so a test can assert the predicate shape."""

    def __init__(self) -> None:
        self.sqls: list[str] = []
        self.params: list[object] = []

    async def execute(self, sql: str, *params: object) -> None:
        self.sqls.append(sql)
        self.params.append(params[0] if params else None)

    async def fetchall(self) -> list[dict[str, object]]:
        return [{"agent": "a", "n": 1}]

    async def fetchone(self) -> dict[str, object]:
        return {"n": 1}


@pytest.mark.asyncio
async def test_dedup_org_total_excludes_synthetic_turns_when_asked() -> None:
    # ADR 0040: the Flotte rollup counts REAL traffic — a validated ``synthetic_col``
    # injects a fixed ``NOT <ident>`` predicate into every sub-query (never raw SQL).
    cur = _RecordingCursor()
    await dedup_org_total(
        cur,  # type: ignore[arg-type]
        table="conversation_messages",
        entity_col="conversation_id",
        synthetic_col="synthetic",
    )
    assert cur.sqls  # per-agent + org + shared
    assert all("NOT synthetic" in s for s in cur.sqls)


@pytest.mark.asyncio
async def test_dedup_org_total_has_no_synthetic_predicate_by_default() -> None:
    cur = _RecordingCursor()
    await dedup_org_total(
        cur,  # type: ignore[arg-type]
        table="conversation_messages",
        entity_col="conversation_id",
    )
    assert cur.sqls
    assert all("synthetic" not in s for s in cur.sqls)


@pytest.mark.asyncio
async def test_dedup_org_total_rejects_an_unsafe_synthetic_identifier() -> None:
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        await dedup_org_total(
            _RecordingCursor(),  # type: ignore[arg-type]
            table="conversation_messages",
            entity_col="conversation_id",
            synthetic_col="synthetic OR true --",
        )


@pytest.mark.asyncio
async def test_dedup_org_total_scopes_every_count_to_the_requested_window() -> None:
    """A conversation before the selected period must not survive through the dedup seam."""
    cur = _RecordingCursor()
    since = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    until = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)

    await dedup_org_total(
        cur,  # type: ignore[arg-type]
        table="conversation_messages",
        entity_col="conversation_id",
        synthetic_col="synthetic",
        time_col="created_at",
        since=since,
        until=until,
    )

    assert len(cur.sqls) == 3
    assert all("created_at >= %s" in sql for sql in cur.sqls)
    assert all("created_at <= %s" in sql for sql in cur.sqls)
    assert all(params == (since, until) for params in cur.params)


@pytest.mark.asyncio
async def test_shared_entities_among_excludes_synthetic_turns_when_asked() -> None:
    cur = _RecordingCursor()
    await shared_entities_among(
        cur,  # type: ignore[arg-type]
        table="conversation_messages",
        entity_col="conversation_id",
        entities={"c1", "c2"},
        synthetic_col="synthetic",
    )
    assert any("AND NOT synthetic" in s for s in cur.sqls)

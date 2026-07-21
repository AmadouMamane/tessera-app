"""``list_conversations`` is a real-traffic read (ADR 0040).

The transcript module promises that every "real traffic" read excludes
synthetic turns — yet the conversation list that feeds the business
console's "Récents" and the cockpit Historique (CT-01) shipped without
the predicate, so an operator trial showed up as a customer
conversation. This witness makes the promise loud: it records the SQL
the function actually executes and asserts the exclusion is in it.
"""

from __future__ import annotations

import pytest

from tessera.memory import transcript


class _RecordingCursor:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __aenter__(self) -> _RecordingCursor:
        return self

    async def __aexit__(self, *_a: object) -> bool:
        return False

    async def execute(self, query: object, *_params: object) -> None:
        as_string = getattr(query, "as_string", None)
        self._log.append(as_string(None) if callable(as_string) else str(query))

    async def fetchall(self) -> list[dict[str, object]]:
        return []


class _RecordingConn:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def __aenter__(self) -> _RecordingConn:
        return self

    async def __aexit__(self, *_a: object) -> bool:
        return False

    def cursor(self, *, row_factory: object | None = None) -> _RecordingCursor:
        assert row_factory is not None, "the reader must scope its row factory to the cursor"
        return _RecordingCursor(self._log)


class _RecordingPool:
    closed = False

    def __init__(self, log: list[str]) -> None:
        self._log = log

    def connection(self) -> _RecordingConn:
        return _RecordingConn(self._log)


@pytest.mark.asyncio
async def test_list_conversations_excludes_synthetic_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    monkeypatch.setattr(transcript, "get_pool", lambda: _RecordingPool(log))
    await transcript.list_conversations("support-client")
    assert log, "the read must reach the cursor"
    # The outer aggregate AND the title subquery both read real traffic only.
    assert all("NOT m.synthetic" in q for q in log)
    assert all("NOT u.synthetic" in q for q in log)

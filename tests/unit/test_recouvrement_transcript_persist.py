"""Unit tests: the recouvrement message route writes the durable transcript (ADR 0040).

Before ADR 0040 the recouvrement structured turn emitted ~30 business events but never
wrote ``conversation_messages``, so the agent's Synthèse read a false zero. These tests
pin the persistence CONTRACT at the route seam — ``append_messages`` is monkeypatched, so
no Postgres is needed — the way the durable write is exercised end to end is the
integration suite's job.
"""

from __future__ import annotations

from typing import Any

import pytest

from tessera.api.routes import recouvrement_assistant as ra
from tessera.authz import Surface


def _req(**over: Any) -> ra.RecouvrementAssistantRequest:
    base: dict[str, Any] = {"message": "Bonjour, je veux échelonner ma dette."}
    base.update(over)
    return ra.RecouvrementAssistantRequest(**base)


class _Recorder:
    """Captures the single ``append_messages`` call the route makes."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def append(self, conv: Any, turn: Any, messages: Any, **kw: Any) -> None:
        self.calls.append({"conv": conv, "turn": turn, "messages": messages, **kw})


@pytest.mark.asyncio
async def test_persist_attributes_agent_case_and_marks_real_traffic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    monkeypatch.setattr(ra, "append_messages", rec.append)

    await ra._persist_recouvrement_turn(
        _req(case_id="RC-9", surface="dedicated-ui"),
        {"visibleReply": "Voici un échéancier proposé."},
        latency_ms=123.0,
    )

    assert len(rec.calls) == 1
    call = rec.calls[0]
    # Attributed to the recouvrement agent (never the transcript default support-client),
    # to the served case, at real latency, and NOT a test turn.
    assert call["agent_id"] == "recouvrement"
    assert call["subject_id"] == "RC-9"
    assert call["latency_ms"] == 123.0
    assert call["synthetic"] is False
    # A user turn (masked) + the assistant's visible reply, in order.
    roles = [(m.role, m.content) for m in call["messages"]]
    assert roles[0][0] == "user"
    assert "échelonner ma dette" in roles[0][1]
    assert roles[1] == ("assistant", "Voici un échéancier proposé.")


@pytest.mark.asyncio
async def test_persist_marks_operator_test_surface_synthetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    monkeypatch.setattr(ra, "append_messages", rec.append)

    await ra._persist_recouvrement_turn(
        _req(surface=Surface.COCKPIT_EMBEDDED.value),
        {"visibleReply": "réponse de test"},
        latency_ms=10.0,
    )

    # A Console-embedded (operator TEST) recouvrement turn is written but marked, so it
    # never inflates the agent's Synthèse — the symmetric half of ADR 0040.
    assert rec.calls[0]["synthetic"] is True


@pytest.mark.asyncio
async def test_persist_skips_when_the_graph_has_no_visible_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rec = _Recorder()
    monkeypatch.setattr(ra, "append_messages", rec.append)

    await ra._persist_recouvrement_turn(_req(), {"visibleReply": ""}, latency_ms=5.0)
    await ra._persist_recouvrement_turn(_req(), {}, latency_ms=5.0)

    # No assistant content ⇒ nothing to record; a half-written turn is not persisted.
    assert rec.calls == []


@pytest.mark.asyncio
async def test_persist_degrades_and_never_raises_when_the_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*_a: Any, **_kw: Any) -> None:
        raise RuntimeError("postgres down")

    monkeypatch.setattr(ra, "append_messages", _boom)

    # A persistence failure must never break the operator's turn — it degrades to stderr.
    await ra._persist_recouvrement_turn(_req(), {"visibleReply": "ok"}, latency_ms=1.0)


@pytest.mark.asyncio
async def test_persist_mints_uuids_for_a_non_uuid_client_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uuid

    rec = _Recorder()
    monkeypatch.setattr(ra, "append_messages", rec.append)

    await ra._persist_recouvrement_turn(
        _req(conversation_id="not-a-uuid", turn_id="also-bad"),
        {"visibleReply": "ok"},
        latency_ms=1.0,
    )

    # A malformed client id must not lose the turn to a broken uuid column: fresh ids.
    call = rec.calls[0]
    assert isinstance(call["conv"], uuid.UUID)
    assert isinstance(call["turn"], uuid.UUID)

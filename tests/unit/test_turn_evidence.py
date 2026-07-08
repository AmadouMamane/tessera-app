"""Turn-evidence read — the L1 fact that folds real emission into the level (ADR 0017 §F).

Evidence is the Prometheus ``tessera_agent_turns_total`` counter. The read is gated (shipped
off, like every 0015/0017 store flip) and honest-empty: evidence-*unknown* (disabled or store
unreachable) is trusted, never treated as absence — so an outage never demotes a live agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tessera.observability import turn_evidence
from tessera.observability.spine.adapters.base import SpineUnavailableError

if TYPE_CHECKING:
    import pytest

_FLAG = "TESSERA_LEVEL_TURN_EVIDENCE"


def _row(agent_id: str, count: float) -> dict[str, object]:
    return {"metric": {"agent_id": agent_id}, "value": [1700000000, str(count)]}


def test_disabled_by_default_is_unknown_and_trusted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_FLAG, raising=False)
    assert turn_evidence.turn_evidence_enabled() is False
    assert turn_evidence.agents_with_turn_evidence() is None  # unknown, not absent
    # Evidence-unknown → trust the declared contract (never demote).
    assert turn_evidence.has_turn_evidence("hello-agent") is True


def test_enabled_reads_the_prometheus_turn_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_FLAG, "1")
    monkeypatch.setattr(
        turn_evidence.PrometheusAdapter,
        "instant",
        lambda _self, _query, **_k: [_row("hello-agent", 3), _row("idle-agent", 0)],
    )
    observed = turn_evidence.agents_with_turn_evidence()
    assert observed == {"hello-agent"}  # idle-agent's 0-count is not evidence
    assert turn_evidence.has_turn_evidence("hello-agent", observed) is True
    assert turn_evidence.has_turn_evidence("idle-agent", observed) is False
    assert turn_evidence.has_turn_evidence("unknown-agent", observed) is False


def test_unreachable_store_is_unknown_not_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_FLAG, "1")

    def _down(_self: object, _query: str, **_k: object) -> list[dict[str, object]]:
        raise SpineUnavailableError("prometheus down")

    monkeypatch.setattr(turn_evidence.PrometheusAdapter, "instant", _down)
    assert turn_evidence.agents_with_turn_evidence() is None
    # A transient outage must not drop a live agent to L0 — unknown is trusted.
    assert turn_evidence.has_turn_evidence("hello-agent") is True


def test_empty_agent_id_has_no_evidence() -> None:
    assert turn_evidence.has_turn_evidence(None) is False
    assert turn_evidence.has_turn_evidence("") is False

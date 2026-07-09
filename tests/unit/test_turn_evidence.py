"""Turn-evidence read — the L1 fact that folds real emission into the level (ADR 0017 §F).

Evidence is the Prometheus ``tessera_agent_turns_total`` counter. The read is gated (shipped
off, like every 0015/0017 store flip). Evidence-*unknown* used to be **trusted as observed**,
which handed out a computed-looking L1 resting on an assumption; it now yields no proof, and
the caller distinguishes ``unverifiable`` (store off or down) from ``dormant`` (store read,
agent silent) so the badge can say which.
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


def test_disabled_by_default_is_unverifiable_never_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(_FLAG, raising=False)
    assert turn_evidence.turn_evidence_enabled() is False
    assert turn_evidence.agents_with_turn_evidence() is None  # unknown, not absent
    # Unknown is not evidence. A cockpit that observes nothing computes no rung from it.
    assert turn_evidence.turn_evidence_state("hello-agent") == "unverifiable"
    assert turn_evidence.has_turn_evidence("hello-agent") is False


def test_enabled_reads_the_prometheus_turn_counter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_FLAG, "1")
    monkeypatch.setattr(
        turn_evidence.PrometheusAdapter,
        "instant",
        lambda _self, _query, **_k: [_row("hello-agent", 3), _row("idle-agent", 0)],
    )
    observed = turn_evidence.agents_with_turn_evidence()
    assert observed == {"hello-agent"}  # idle-agent's 0-count is not evidence
    assert turn_evidence.turn_evidence_state("hello-agent", observed) == "observed"
    assert turn_evidence.has_turn_evidence("hello-agent", observed) is True
    # Store read, agent silent → dormant. Its silence, not the store's.
    assert turn_evidence.turn_evidence_state("idle-agent", observed) == "dormant"
    assert turn_evidence.has_turn_evidence("idle-agent", observed) is False
    assert turn_evidence.turn_evidence_state("unknown-agent", observed) == "dormant"


def test_unreachable_store_is_unverifiable_not_dormant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_FLAG, "1")

    def _down(_self: object, _query: str, **_k: object) -> list[dict[str, object]]:
        raise SpineUnavailableError("prometheus down")

    monkeypatch.setattr(turn_evidence.PrometheusAdapter, "instant", _down)
    assert turn_evidence.agents_with_turn_evidence() is None
    # An outage cannot disprove emission — but it cannot prove it either. The two silences
    # stay distinguishable so the badge never blames a live agent for a dead store.
    assert turn_evidence.turn_evidence_state("hello-agent") == "unverifiable"
    assert turn_evidence.has_turn_evidence("hello-agent") is False


def test_empty_agent_id_has_no_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_FLAG, "1")
    monkeypatch.setattr(
        turn_evidence.PrometheusAdapter, "instant", lambda _self, _q, **_k: [_row("a", 1)]
    )
    assert turn_evidence.has_turn_evidence(None) is False
    assert turn_evidence.has_turn_evidence("") is False


def test_the_evidence_query_measures_no_recency_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard the wording: nothing here is windowed, so no label may promise "recent".

    ``tessera_agent_turns_total`` is a cumulative counter read as an instant vector. "Dormant"
    means "no turn observed over the store's retention", not "no turn in the last N hours".
    The day someone wraps it in ``increase(...[24h])``, evidence changes meaning — this test
    fails, and the UI wording must be revisited in the same breath.
    """
    monkeypatch.setenv(_FLAG, "1")
    seen: list[str] = []

    def _capture(_self: object, query: str, **_k: object) -> list[dict[str, object]]:
        seen.append(query)
        return []

    monkeypatch.setattr(turn_evidence.PrometheusAdapter, "instant", _capture)
    turn_evidence.agents_with_turn_evidence()
    assert seen == ["sum by (agent_id) (tessera_agent_turns_total)"]
    assert "[" not in seen[0], "a range selector would make the evidence windowed"

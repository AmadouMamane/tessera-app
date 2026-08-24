"""The understanding summary reads the thing — comparison rows — and says its window.

ADR 0053 / ADR 0017 §A5.3: counts only, failures named by kind, freshness carried,
``None`` for an agent with no classified turns (an absent plane, not an empty score),
and the fleet-wide read never aggregates it (populations of different agents are not
one population).
"""

from __future__ import annotations

import pytest

from tessera.guard.audit import AGENT_TURN_ACTOR
from tessera.observability import business_capabilities, business_events as bev
from tessera.observability.understanding_read import UNDERSTANDING_WINDOW, understanding_summary


@pytest.fixture(autouse=True)
def _memory_ledger() -> None:
    bev.set_business_event_store(bev.InMemoryBusinessEventStore())


def _record_shadow(
    turn: str,
    *,
    status: str = "verdict",
    agree: bool | None = True,
    latency: float = 2000.0,
    mode: str = "shadow",
    model: str = "gemma3:27b",
) -> None:
    bev.record_business_event(
        author=AGENT_TURN_ACTOR,
        event_name=bev.BusinessEventName.INTENT_ROUTED,
        payload={
            "shadow": True,
            "mode": mode,
            "llm_status": status,
            "schema_valid": status == "verdict",
            "agree": agree if status == "verdict" else None,
            "llm_latency_ms": latency,
        },
        agent_id="recouvrement",
        workflow_id="recouvrement_collections_v1",
        capability_id=None,
        surface="dedicated-ui",
        conversation_id="conv-read",
        turn_id=turn,
        case_id="RC-2048",
        node_name="shadow_understanding",
        language="fr",
        model=model,
        environment="dev",
    )


def test_no_comparison_rows_is_none_not_zero() -> None:
    """An agent with no classified turns has no understanding plane to report."""
    assert understanding_summary("recouvrement") is None


def test_counts_add_up_and_failures_are_named() -> None:
    _record_shadow("t1", status="verdict", agree=True, latency=1000.0)
    _record_shadow("t2", status="verdict", agree=False, latency=3000.0)
    _record_shadow("t3", status="timeout")
    _record_shadow("t4", status="schema_invalid")
    summary = understanding_summary("recouvrement")
    assert summary is not None
    assert summary["observed"] == 4
    assert summary["verdicts"] == 2
    assert summary["agree"] == 1
    assert summary["disagree"] == 1
    assert summary["failures"] == {"timeout": 1, "schema_invalid": 1}
    assert summary["latency_ms_p50"] == 3000.0  # median of the VERDICT population only
    assert summary["window"] == UNDERSTANDING_WINDOW


def test_latest_row_names_mode_model_and_freshness() -> None:
    _record_shadow("t1", mode="shadow", model="llama3.2:3b")
    _record_shadow("t2", mode="active", model="gemma3:27b")
    summary = understanding_summary("recouvrement")
    assert summary is not None
    assert summary["latest_mode"] == "active"
    assert summary["latest_model"] == "gemma3:27b"
    assert summary["latest_at"] is not None


def test_capabilities_aggregate_carries_the_block_for_one_agent_never_the_fleet() -> None:
    """The third ruler is per-agent; an 'all' read answers None, never a merged count."""
    _record_shadow("t1")
    scoped = business_capabilities.business_capability_aggregate(agent_id="recouvrement")
    fleet = business_capabilities.business_capability_aggregate(agent_id=None)
    assert scoped["understanding"] is not None
    assert scoped["understanding"]["observed"] == 1  # type: ignore[index]
    assert fleet["understanding"] is None


def test_only_shadow_rows_count_not_the_routers_own_intent_events() -> None:
    """The router's intent.routed rows are routing, not comparison — excluded by node."""
    bev.record_business_event(
        author=AGENT_TURN_ACTOR,
        event_name=bev.BusinessEventName.INTENT_ROUTED,
        payload={"intent": "summarize_case", "intent_source": "regex"},
        agent_id="recouvrement",
        workflow_id="recouvrement_collections_v1",
        capability_id=None,
        surface="dedicated-ui",
        conversation_id="conv-read",
        turn_id="t-route",
        case_id="RC-2048",
        node_name="route_recouvrement_intent",
        language="fr",
        model="recouvrement_collections_v1",
        environment="dev",
    )
    assert understanding_summary("recouvrement") is None

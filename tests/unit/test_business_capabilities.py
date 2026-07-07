"""Unit tests for the per-capability business aggregate."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from tessera.agent.recouvrement import RECOUVREMENT_AGENT_ID, RECOUVREMENT_WORKFLOW_ID
from tessera.observability import business_capabilities, business_events

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def in_memory_business_events(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    previous_store = business_events.get_business_event_store()
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "jsonl")
    business_events.set_business_event_store(business_events.InMemoryBusinessEventStore())
    business_events.reset_business_event_store()
    try:
        yield
    finally:
        business_events.reset_business_event_store()
        business_events.set_business_event_store(previous_store)


def test_unknown_capability_row_is_rendered_as_non_attribue(
    in_memory_business_events: None,
) -> None:
    business_events.record_business_event(
        event_name=business_events.BusinessEventName.INTENT_ROUTED,
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        conversation_id="conv-unknown-capability",
        turn_id="turn-unknown-capability",
        case_id="RC-2048",
        payload={"intent": "legacy", "confidence": 0.42, "active_task": ""},
    )

    aggregate = business_capabilities.business_capability_aggregate(
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        conversation_id="conv-unknown-capability",
    )

    capabilities = cast("list[dict[str, object]]", aggregate["capabilities"])
    rows = {str(row["capability_id"]): row for row in capabilities}
    unknown = rows[business_capabilities.UNKNOWN_CAPABILITY_ID]

    assert aggregate["unknown_capability_id"] == business_capabilities.UNKNOWN_CAPABILITY_ID
    assert aggregate["unknown_capability_label"] == business_capabilities.UNKNOWN_CAPABILITY_LABEL
    assert business_capabilities.UNKNOWN_CAPABILITY_LABEL == "non attribué"
    assert unknown["label"] == business_capabilities.UNKNOWN_CAPABILITY_LABEL
    assert unknown["label_key"] is None
    assert unknown["volume"] == 1


def test_conformity_is_unknown_when_only_diagnostic_trace_score_exists(
    in_memory_business_events: None,
) -> None:
    business_events.record_business_event(
        event_name=business_events.BusinessEventName.CASE_CONTEXT_LOADED,
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        capability_id="summarize_case",
        conversation_id="conv-summary-diagnostic-only",
        turn_id="turn-summary-diagnostic-only",
        case_id="RC-2048",
        payload={"client": "M. D.", "amount_due": 840, "days_late": 32},
    )

    aggregate = business_capabilities.business_capability_aggregate(
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        conversation_id="conv-summary-diagnostic-only",
    )

    capabilities = cast("list[dict[str, object]]", aggregate["capabilities"])
    rows = {str(row["capability_id"]): row for row in capabilities}

    assert rows["summarize_case"]["volume"] == 1
    assert rows["summarize_case"]["conformity_pct"] is None

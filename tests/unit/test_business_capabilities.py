"""Unit tests for the per-capability business aggregate."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from tessera.agent.recouvrement import RECOUVREMENT_AGENT_ID, RECOUVREMENT_WORKFLOW_ID
from tessera.authz import Actor
from tessera.observability import business_capabilities, business_events
from tessera.recouvrement.scoring import ensure_recouvrement_scorer_registered

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def in_memory_business_events(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    previous_store = business_events.get_business_event_store()
    monkeypatch.setenv("TESSERA_SPINE_SOURCE_BUSINESS_EVENTS", "local")
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
        author=Actor.system("test-fixture"),
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
        author=Actor.system("test-fixture"),
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


def test_business_signals_are_aggregated_per_run(
    in_memory_business_events: None,
) -> None:
    ensure_recouvrement_scorer_registered()
    business_events.record_business_event(
        author=Actor.system("test-fixture"),
        event_name=business_events.BusinessEventName.ACTION_PREPARED,
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        capability_id="propose_schedule",
        conversation_id="conv-action-signal",
        turn_id="turn-legacy-missing-flags",
        case_id="RC-2048",
        node_name="legacy",
        decision="prepared",
        payload={"action_name": "prepare_schedule_proposal"},
    )
    business_events.record_business_event(
        author=Actor.system("test-fixture"),
        event_name=business_events.BusinessEventName.ACTION_PREPARED,
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        capability_id="propose_schedule",
        conversation_id="conv-action-signal",
        turn_id="turn-current-traceable",
        case_id="RC-2048",
        node_name="current",
        artifact_id="RC-2048-schedule-36-months-v2",
        artifact_type="schedule_proposal_v2",
        artifact_status="draft",
        decision="prepared",
        payload={
            "action_name": "prepare_schedule_proposal",
            "artifact_id": "RC-2048-schedule-36-months-v2",
            "artifact_type": "schedule_proposal_v2",
            "case_id": "RC-2048",
            "requires_validation": True,
            "no_external_effect": True,
        },
    )

    aggregate = business_capabilities.business_capability_aggregate(
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        conversation_id="conv-action-signal",
    )

    signals = cast("list[dict[str, object]]", aggregate["business_signals"])
    by_signal = {str(row["key"]): row for row in signals}

    assert by_signal["action_governance"]["value_pct"] == 50.0
    assert by_signal["action_governance"]["reason"] == "scored_runs_mean"
    assert by_signal["no_uncontrolled_external_effect"]["value_pct"] == 50.0
    assert by_signal["no_uncontrolled_external_effect"]["reason"] == "scored_runs_mean"


def test_signal_evidence_counts_real_runs_checks_and_the_last_look(
    in_memory_business_events: None,
) -> None:
    """P3 item 18 — what the hero card shows when a signal is not decisive.

    Two runs of `propose_schedule`: the legacy one carries no traceability flags (the scorer
    cannot score `action_governance` on it), the current one does. So the signal is *observed*
    twice and *checked* once, and `last_checked_at` is a real event timestamp — none of it
    inferred, none of it fabricated.
    """
    ensure_recouvrement_scorer_registered()
    for turn_id, payload in (
        ("turn-legacy-missing-flags", {"action_name": "prepare_schedule_proposal"}),
        (
            "turn-current-traceable",
            {
                "action_name": "prepare_schedule_proposal",
                "artifact_id": "RC-2048-schedule-36-months-v2",
                "artifact_type": "schedule_proposal_v2",
                "case_id": "RC-2048",
                "requires_validation": True,
                "no_external_effect": True,
            },
        ),
    ):
        business_events.record_business_event(
            author=Actor.system("test-fixture"),
            event_name=business_events.BusinessEventName.ACTION_PREPARED,
            agent_id=RECOUVREMENT_AGENT_ID,
            workflow_id=RECOUVREMENT_WORKFLOW_ID,
            capability_id="propose_schedule",
            conversation_id="conv-evidence",
            turn_id=turn_id,
            case_id="RC-2048",
            decision="prepared",
            payload=payload,
        )

    aggregate = business_capabilities.business_capability_aggregate(
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        conversation_id="conv-evidence",
    )
    signals = cast("list[dict[str, object]]", aggregate["business_signals"])
    by_signal = {str(row["key"]): row for row in signals}

    # DECISIVE — the scorer could evaluate both runs (one scored 1.0, one 0.0: a 0 is still a
    # check, not a missing one). The hero shows the % and says it rests on two checks.
    scored = cast("dict[str, object]", by_signal["action_governance"]["evidence"])
    assert by_signal["action_governance"]["status"] == "scored"
    assert scored["observed_runs"] == 2
    assert scored["checks"] == 2
    assert isinstance(scored["last_checked_at"], str)  # a real event stamp, never "now"

    # ACCUMULATING — the runs were observed, but no contact-window rule applied to either, so
    # the signal has no value. `observed_runs > 0, checks == 0` is precisely what lets the hero
    # say "2 exécutions observées · aucun contrôle applicable" instead of drawing a dash.
    unchecked = cast("dict[str, object]", by_signal["contact_window_compliance"]["evidence"])
    assert by_signal["contact_window_compliance"]["value_pct"] is None
    assert unchecked["observed_runs"] == 2
    assert unchecked["checks"] == 0
    assert isinstance(unchecked["last_checked_at"], str)


def test_signal_evidence_is_all_zeros_when_nothing_was_ever_observed(
    in_memory_business_events: None,
) -> None:
    """The genuine zero-data case — the one that keeps the dash + reason (P3 item 18)."""
    ensure_recouvrement_scorer_registered()
    aggregate = business_capabilities.business_capability_aggregate(
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        conversation_id="conv-that-never-happened",
    )
    signals = cast("list[dict[str, object]]", aggregate["business_signals"])
    for signal in signals:
        evidence = cast("dict[str, object]", signal["evidence"])
        assert evidence == {"observed_runs": 0, "checks": 0, "last_checked_at": None}

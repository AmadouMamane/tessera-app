"""Tests for the minimal specialised Recouvrement graph v1."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from prometheus_client import generate_latest

from tessera.agent.recouvrement import (
    RECOUVREMENT_AGENT_ID,
    RECOUVREMENT_WORKFLOW_ID,
    run_recouvrement_graph_v1,
)
from tessera.api.routes import observability as obs
from tessera.api.routes.recouvrement_assistant import (
    RecouvrementAssistantRequest,
    recouvrement_assistant_message,
)
from tessera.guard import audit
from tessera.observability import (
    business_events as business_events_mod,
    business_scoring as business_scoring_mod,
    metrics,
    replay as replay_mod,
)
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.snapshot import compute_snapshot, reset_snapshot_cache
from tessera.recouvrement.scoring import RecouvrementBusinessScorer
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def observed_recouvrement_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Use temp observability stores for the specialised graph tests."""
    audit_file = tmp_path / "audit.log"
    bundle_file = tmp_path / "bundles.jsonl"
    settings = get_settings()
    monkeypatch.setattr(settings.guard, "audit_file", audit_file)
    monkeypatch.setattr(settings.guard, "audit_sink", "file")
    monkeypatch.setattr(audit, "_last_hash", None)
    previous_store = business_events_mod.get_business_event_store()
    business_events_mod.set_business_event_store(business_events_mod.InMemoryBusinessEventStore())
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: bundle_file)
    business_events_mod.reset_business_event_store()
    replay_mod._BUNDLES.clear()
    monkeypatch.setattr(replay_mod, "_WARMED", False)
    reset_snapshot_cache()
    yield audit_file
    business_events_mod.reset_business_event_store()
    business_events_mod.set_business_event_store(previous_store)
    replay_mod._BUNDLES.clear()
    reset_snapshot_cache()


def test_recouvrement_graph_blocks_call_outside_contact_window(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 21h ?",
        conversation_id="conv-rc-graph",
        turn_id="turn-21h",
    )

    assert "Non, vous ne devez pas appeler M. D. à 21:00" in output["visibleReply"]
    assert "autorisé aujourd'hui uniquement entre 08:00 et 20:00" in output["visibleReply"]
    assert output["artifact"]["type"] == "contact_rule_v1"
    assert output["artifact"]["task"] == "check_rule"
    assert output["artifact"]["status"] == "draft"
    assert output["artifact"]["content"]["requested_time"] == "21:00"
    assert output["artifact"]["content"]["decision"] == "blocked"
    assert output["decisions"]["intent"] == "check_contact_rule"
    assert output["decisions"]["slots"]["requested_time"] == "21:00"
    assert output["decisions"]["contactPolicy"]["decision"] == "blocked"
    assert output["decisions"]["contactPolicy"]["reason_codes"] == ["OUTSIDE_CONTACT_WINDOW"]
    assert "Appel à 21:00 : non autorisé" in output["cardUpdates"]["contactFrame"]
    assert output["suggestedActions"] == [
        "Planifier un rappel demain",
        "Rédiger un email de confirmation",
        "Reporter le contact",
        "Voir la règle de contact",
    ]


@pytest.mark.parametrize("surface", ["dedicated-ui", "cockpit-embedded"])
def test_recouvrement_graph_authorizes_operator_surfaces(
    observed_recouvrement_stores: Path,
    surface: str,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Quand puis-je l'appeler ?",
        conversation_id=f"conv-rc-auth-{surface}",
        turn_id=f"turn-auth-{surface}",
        surface=surface,
    )

    assert output["artifact"]["type"] == "contact_rule_v1"
    assert output["businessEvents"][0]["event_name"] == "case.context_loaded"
    assert not any(
        row["reason_codes"] == ["UNAUTHORIZED_SURFACE"] for row in output["businessEvents"]
    )


@pytest.mark.parametrize("surface", ["public", "support-client", "unknown-surface"])
def test_recouvrement_graph_denies_unauthorized_surfaces_before_business_rule(
    observed_recouvrement_stores: Path,
    surface: str,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 21h ?",
        conversation_id=f"conv-rc-deny-{surface}",
        turn_id=f"turn-deny-{surface}",
        surface=surface,
    )

    assert output["artifact"]["type"] == "authorization_denial_v1"
    assert output["artifact"]["status"] == "blocked"
    assert output["decisions"]["authorization"]["reason_codes"] == ["UNAUTHORIZED_SURFACE"]
    assert [row["event_name"] for row in output["businessEvents"]] == ["action.blocked"]
    assert output["businessEvents"][0]["reason_codes"] == ["UNAUTHORIZED_SURFACE"]
    assert output["businessEvents"][0]["payload"]["action_name"] == "run_recouvrement_workflow"
    assert not any(row["event_name"] == "business_rule.checked" for row in output["businessEvents"])


async def test_recouvrement_graph_projects_business_events_replay_audit_and_metrics(
    observed_recouvrement_stores: Path,
    tmp_path: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 21h ?",
        conversation_id="conv-rc-observed",
        turn_id="turn-21h-observed",
    )

    rows = business_events_mod.business_event_rows(
        agent_id=RECOUVREMENT_AGENT_ID,
        conversation_id="conv-rc-observed",
        turn_id="turn-21h-observed",
    )
    assert [row["event_name"] for row in rows] == [
        "case.context_loaded",
        "intent.routed",
        "slots.extracted",
        "business_rule.checked",
        "policy.decision_made",
        "action.blocked",
        "artifact.created",
        "message.generated",
    ]
    assert output["businessEvents"] == rows
    route_payload = await obs.observability_business_events(
        agent=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        case_id="RC-2048",
        conversation_id="conv-rc-observed",
        turn_id="turn-21h-observed",
        event_name="business_rule.checked",
        decision="blocked",
    )
    assert [row["event_name"] for row in route_payload["events"]] == ["business_rule.checked"]
    assert route_payload["events"][0]["case_id"] == "RC-2048"
    assert route_payload["events"][0]["decision"] == "blocked"
    assert route_payload["workflow_id"] == RECOUVREMENT_WORKFLOW_ID
    unfiltered_route_payload = await obs.observability_business_events(
        agent=RECOUVREMENT_AGENT_ID,
        conversation_id="conv-rc-observed",
        turn_id="turn-21h-observed",
    )
    assert unfiltered_route_payload["events"] == rows
    assert unfiltered_route_payload["scores"] == output["businessScores"]
    snap = await compute_snapshot(
        Scope.from_query({"agent": RECOUVREMENT_AGENT_ID}),
        ["business_events", "recouvrement_business_scores"],
    )
    assert snap["signals"]["business_events"]["data"]["events"] == rows
    assert (
        snap["signals"]["recouvrement_business_scores"]["data"]["scores"]
        == (output["businessScores"])
    )
    rule_event = next(row for row in rows if row["event_name"] == "business_rule.checked")
    assert rule_event["agent_id"] == RECOUVREMENT_AGENT_ID
    assert rule_event["workflow_id"] == RECOUVREMENT_WORKFLOW_ID
    assert rule_event["surface"] == "dedicated-ui"
    assert rule_event["case_id"] == "RC-2048"
    assert rule_event["decision"] == "blocked"
    assert rule_event["reason_codes"] == ["OUTSIDE_CONTACT_WINDOW"]

    action_event = next(row for row in rows if row["event_name"] == "action.blocked")
    assert action_event["payload"]["action_name"] == "prepare_outbound_call"
    artifact_event = next(row for row in rows if row["event_name"] == "artifact.created")
    assert artifact_event["artifact_type"] == "contact_rule_v1"
    assert artifact_event["artifact_status"] == "draft"

    bundles = replay_mod.recent_bundles(agent_id=RECOUVREMENT_AGENT_ID)
    assert len(bundles) == 1
    assert bundles[0].conversation_id == "conv-rc-observed"
    assert bundles[0].turn_id == "turn-21h-observed"
    assert bundles[0].business_events == rows

    audit_rows = [
        json.loads(line)
        for line in observed_recouvrement_stores.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {row["event_name"] for row in audit_rows} == {
        "business_rule.checked",
        "policy.decision_made",
        "action.blocked",
        "artifact.created",
    }
    assert audit.verify_audit_chain(observed_recouvrement_stores).verified is True

    prometheus = generate_latest(metrics.registry).decode("utf-8")
    assert 'tessera_business_rule_checked_total{agent_id="recouvrement"' in prometheus
    assert 'tessera_action_blocked_total{agent_id="recouvrement"' in prometheus
    assert 'tessera_artifact_created_total{agent_id="recouvrement"' in prometheus
    assert not (tmp_path / "business_events.jsonl").exists()


def test_recouvrement_graph_scores_contact_rule_without_false_not_applicable_zero(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 21h ?",
        conversation_id="conv-rc-scores",
        turn_id="turn-21h-scores",
    )

    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["contact_window_compliance"]["score"] == 1.0
    assert scores["action_blocking_correctness"]["score"] == 1.0
    assert scores["artifact_governance"]["score"] == 1.0
    assert scores["recouvrement_trace_completeness"]["score"] > 0.8
    assert scores["validation_required_compliance"]["status"] == "unknown"
    assert scores["validation_required_compliance"]["score"] is None
    assert scores["amount_consistency"]["status"] == "unknown"
    assert scores["amount_consistency"]["score"] is None


def test_recouvrement_business_scorer_is_called_through_registry_without_generic_zero(
    observed_recouvrement_stores: Path,
) -> None:
    registry = business_scoring_mod.BusinessScoringRegistry()
    registry.register(RecouvrementBusinessScorer())
    generic_rows = [
        {
            "event_name": "business_rule.checked",
            "agent_id": "support-client",
            "workflow_id": "support_v1",
            "decision": "allowed",
            "reason_codes": [],
            "payload": {"rule_id": "ACCOUNT_BALANCE"},
        }
    ]

    assert registry.score_rows(generic_rows) == []

    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 21h ?",
        conversation_id="conv-rc-registry",
        turn_id="turn-registry",
    )
    scores = registry.score_rows(output["businessEvents"])
    assert {row["metric"] for row in scores} >= {
        "contact_window_compliance",
        "action_blocking_correctness",
        "artifact_governance",
        "validation_required_compliance",
        "recouvrement_trace_completeness",
        "amount_consistency",
    }
    assert all(row["score"] != 0 for row in scores if row["status"] != "scored")


def test_business_event_payload_validation_and_versioning(
    observed_recouvrement_stores: Path,
) -> None:
    with pytest.raises(business_events_mod.BusinessPayloadValidationError):
        business_events_mod.record_business_event(
            event_name=business_events_mod.BusinessEventName.ACTION_BLOCKED,
            agent_id=RECOUVREMENT_AGENT_ID,
            workflow_id=RECOUVREMENT_WORKFLOW_ID,
            surface="dedicated-ui",
            conversation_id="conv-invalid-payload",
            turn_id="turn-invalid-payload",
            case_id="RC-2048",
            node_name="test",
            decision="blocked",
            reason_codes=["OUTSIDE_CONTACT_WINDOW"],
            payload={"requested_time": "22:00"},
        )

    event = business_events_mod.record_business_event(
        event_name=business_events_mod.BusinessEventName.BUSINESS_RULE_CHECKED,
        agent_id=RECOUVREMENT_AGENT_ID,
        workflow_id=RECOUVREMENT_WORKFLOW_ID,
        surface="dedicated-ui",
        conversation_id="conv-valid-payload",
        turn_id="turn-valid-payload",
        case_id="RC-2048",
        node_name="test",
        decision="blocked",
        reason_codes=["OUTSIDE_CONTACT_WINDOW"],
        payload={
            "rule_id": "CONTACT_WINDOW",
            "requested_time": "22:00",
            "allowed_window": "08:00-20:00",
            "recommended_channel": "appel sortant",
        },
    )
    row = event.to_row()
    assert row["schema_version"] == "business_event.v1"
    assert row["event_version"] == 1
    assert row["version"] == 1


async def test_recouvrement_assistant_endpoint_returns_structured_contract(
    observed_recouvrement_stores: Path,
) -> None:
    payload = RecouvrementAssistantRequest(
        case_id="RC-2048",
        message="Comment le contacter ?",
        conversation_id="conv-rc-endpoint",
        turn_id="turn-endpoint",
        assistant_state={"activeTask": "check_rule"},
    )
    output = await recouvrement_assistant_message(payload)

    assert output["artifact"]["type"] == "contact_rule_v1"
    assert output["artifact"]["title"] == "Cadre de contact — RC-2048"
    assert "visibleReply" in output
    assert output["cardUpdates"]["context"][0] == "Dossier : RC-2048"
    assert output["suggestedActions"] == [
        "Préparer un script d'appel",
        "Rédiger un email de confirmation",
        "Reporter le contact",
        "Voir la règle de contact",
    ]

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
    metrics,
    replay as replay_mod,
)
from tessera.observability.spine.scope import Scope
from tessera.observability.spine.snapshot import compute_snapshot, reset_snapshot_cache
from tessera.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def observed_recouvrement_stores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Use temp observability stores for the specialised graph tests."""
    audit_file = tmp_path / "audit.log"
    business_file = tmp_path / "business_events.jsonl"
    bundle_file = tmp_path / "bundles.jsonl"
    settings = get_settings()
    monkeypatch.setattr(settings.guard, "audit_file", audit_file)
    monkeypatch.setattr(settings.guard, "audit_sink", "file")
    monkeypatch.setattr(audit, "_last_hash", None)
    monkeypatch.setattr(business_events_mod, "_business_events_path", lambda: business_file)
    monkeypatch.setattr(replay_mod, "_bundles_path", lambda: bundle_file)
    business_events_mod.reset_business_event_store()
    replay_mod._BUNDLES.clear()
    monkeypatch.setattr(replay_mod, "_WARMED", False)
    reset_snapshot_cache()
    yield audit_file
    business_events_mod.reset_business_event_store()
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


async def test_recouvrement_graph_projects_business_events_replay_audit_and_metrics(
    observed_recouvrement_stores: Path,
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
        conversation_id="conv-rc-observed",
        turn_id="turn-21h-observed",
    )
    assert route_payload["events"] == rows
    assert route_payload["scores"] == output["businessScores"]
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
    assert action_event["payload"]["action"] == "prepare_outbound_call"
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

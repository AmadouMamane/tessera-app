"""Tests for the minimal specialised Recouvrement graph v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from prometheus_client import generate_latest

from tessera.agent.recouvrement import (
    RECOUVREMENT_AGENT_ID,
    RECOUVREMENT_WORKFLOW_ID,
    run_recouvrement_action_workflow_v1,
    run_recouvrement_graph_v1,
)
from tessera.api.routes import observability as obs
from tessera.api.routes.recouvrement_assistant import (
    RecouvrementAssistantActionRequest,
    RecouvrementAssistantRequest,
    recouvrement_assistant_action,
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


def test_recouvrement_graph_summarizes_case_without_external_effects(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Résumer ce dossier",
        conversation_id="conv-rc-summary",
        turn_id="turn-summary",
        assistant_state={"activeTask": "summary"},
    )

    artifact = output["artifact"]
    content = artifact["content"]
    assert output["visibleReply"] == "Résumé du dossier RC-2048 mis à jour."
    assert artifact["type"] == "case_summary_v1"
    assert artifact["task"] == "summary"
    assert artifact["status"] == "draft"
    assert artifact["title"] == "Résumé du dossier — RC-2048"
    assert content["amount_due"] == "840,00 €"
    assert content["days_late"] == 32
    assert content["missed_promise"] == "promesse de paiement non tenue le 12 juin"
    assert content["message_sent"] is False
    assert content["schedule_created"] is False
    assert content["no_external_effect"] is True
    assert "promesse de paiement non tenue le 12 juin" in content["summary"]
    assert output["suggestedActions"] == [
        "Rédiger une relance",
        "Vérifier une règle",
        "Proposer un échéancier",
        "Insérer dans le dossier",
    ]
    assert output["decisions"]["intent"] == "summarize_case"
    assert output["decisions"]["summaryPolicy"]["policy_review_status"] == "approved"
    event_names = [row["event_name"] for row in output["businessEvents"]]
    assert event_names == [
        "case.context_loaded",
        "intent.routed",
        "slots.extracted",
        "policy.decision_made",
        "artifact.created",
        "message.generated",
    ]
    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["artifact_governance"]["score"] == 1.0
    assert scores["recouvrement_trace_completeness"]["score"] == 1.0
    assert scores["amount_consistency"]["score"] == 1.0
    assert scores["no_uncontrolled_external_effect"]["score"] == 1.0
    assert scores["client_message_safety"]["status"] == "not_applicable"
    assert scores["contact_window_compliance"]["status"] == "not_applicable"


def test_recouvrement_graph_proposes_schedule_with_backend_observability(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="ok puis-je lui proposer un étalement sur 36 mois ?",
        conversation_id="conv-rc-schedule",
        turn_id="turn-schedule-36",
        assistant_state={"activeTask": "check_rule"},
    )

    assert output["decisions"]["intent"] == "propose_schedule"
    assert output["decisions"]["slots"]["requested_months"] == 36
    assert output["decisions"]["slots"]["monthly_amount"] == 23.33
    assert output["artifact"]["type"] == "schedule_proposal_v2"
    assert output["artifact"]["task"] == "propose_schedule"
    assert output["artifact"]["status"] == "draft"
    assert output["artifact"]["title"] == "Proposition d'échéancier — RC-2048"
    assert output["artifact"]["content"]["amount_due"] == "840,00 €"
    assert output["artifact"]["content"]["duration_months"] == 36
    assert output["artifact"]["content"]["monthly_amount"] == "23,33 €"
    assert output["artifact"]["content"]["validation_required"] is True
    assert output["artifact"]["content"]["client_agreement_required"] is True
    assert output["artifact"]["content"]["schedule_created"] is False
    assert "23,33 €" in output["visibleReply"]
    assert "Aucun échéancier n'a été créé" in output["visibleReply"]
    assert output["cardUpdates"]["paymentPlan"] == [
        "Échéancier indicatif — 36 mois",
        "Montant dû : 840,00 €",
        "Durée demandée : 36 mois",
        "Mensualité indicative : 23,33 €",
        "Statut : validation requise avant proposition",
        "Échéancier non créé",
        "Accord client requis",
    ]
    assert output["cardUpdates"]["clientMessage"] == [
        (
            "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de "
            "validation et d'accord sur les modalités."
        )
    ]
    assert output["suggestedActions"] == [
        "Ajuster la durée",
        "Comparer les options",
        "Préparer le message client",
        "Soumettre à validation",
    ]

    rows = output["businessEvents"]
    assert [row["event_name"] for row in rows] == [
        "case.context_loaded",
        "intent.routed",
        "slots.extracted",
        "business_rule.checked",
        "policy.decision_made",
        "artifact.created",
        "validation.requested",
        "action.prepared",
        "message.generated",
    ]
    assert next(row for row in rows if row["event_name"] == "business_rule.checked")[
        "payload"
    ]["rule_id"] == "SCHEDULE_VALIDATION"
    assert next(row for row in rows if row["event_name"] == "action.prepared")["payload"][
        "action_name"
    ] == "prepare_schedule_proposal"
    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["validation_required_compliance"]["score"] == 1.0
    assert scores["artifact_governance"]["score"] == 1.0
    assert scores["recouvrement_trace_completeness"]["score"] > 0.8
    assert scores["amount_consistency"]["score"] == 1.0
    assert scores["contact_window_compliance"]["status"] == "not_applicable"
    assert scores["contact_window_compliance"]["score"] is None


def test_recouvrement_graph_routes_schedule_follow_up_after_blocked_contact(
    observed_recouvrement_stores: Path,
) -> None:
    contact = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 23h ?",
        conversation_id="conv-rc-followup",
        turn_id="turn-contact-23",
    )
    schedule = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="ok puis je lui proposer un étalement sur 36 mois",
        conversation_id="conv-rc-followup",
        turn_id="turn-schedule-followup",
        assistant_state={
            "activeTask": "check_rule",
            "currentArtifact": contact["artifact"],
        },
    )

    assert contact["decisions"]["intent"] == "check_contact_rule"
    assert contact["artifact"]["content"]["decision"] == "blocked"
    assert schedule["decisions"]["intent"] == "propose_schedule"
    assert schedule["artifact"]["type"] == "schedule_proposal_v2"
    assert schedule["artifact"]["content"]["monthly_amount"] == "23,33 €"
    assert not any(
        row["event_name"] == "business_rule.checked"
        and row["payload"].get("rule_id") == "CONTACT_WINDOW"
        for row in schedule["businessEvents"]
    )


def test_recouvrement_graph_routes_relance_with_duration_to_schedule(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="ok puis-je lui proposer une relance avec un paiement sur 24 mois ?",
        conversation_id="conv-rc-relance-schedule",
        turn_id="turn-relance-schedule",
        assistant_state={"activeTask": "propose_schedule"},
    )

    assert output["decisions"]["intent"] == "propose_schedule"
    assert output["decisions"]["slots"]["requested_months"] == 24
    assert output["artifact"]["type"] == "schedule_proposal_v2"
    assert output["artifact"]["content"]["monthly_amount"] == "35,00 €"
    assert output["artifact"]["content"]["schedule_created"] is False


def test_recouvrement_graph_denies_schedule_on_unauthorized_surface(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Peut-on étaler sur 36 mois ?",
        conversation_id="conv-rc-schedule-deny",
        turn_id="turn-schedule-deny",
        surface="public",
    )

    assert output["artifact"]["type"] == "authorization_denial_v1"
    assert output["decisions"]["authorization"]["reason_codes"] == ["UNAUTHORIZED_SURFACE"]
    assert [row["event_name"] for row in output["businessEvents"]] == ["action.blocked"]


def test_recouvrement_graph_drafts_reminder_without_sending_message(
    observed_recouvrement_stores: Path,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Rédiger une relance",
        conversation_id="conv-rc-draft",
        turn_id="turn-draft",
        assistant_state={"activeTask": "draft_reminder"},
    )

    assert output["decisions"]["intent"] == "draft_reminder"
    assert output["artifact"]["type"] == "reminder_draft_v1"
    assert output["artifact"]["task"] == "draft_reminder"
    assert output["artifact"]["status"] == "draft"
    assert output["artifact"]["title"] == "Brouillon de relance — RC-2048"
    assert output["artifact"]["content"]["message_sent"] is False
    assert output["artifact"]["content"]["no_email_sent"] is True
    assert output["artifact"]["content"]["no_message_sent"] is True
    assert output["artifact"]["content"]["no_schedule_created"] is True
    assert output["artifact"]["content"]["schedule_created"] is False
    assert output["artifact"]["content"]["validation_required"] is False
    assert output["artifact"]["content"]["generation_mode"] == "approved_template"
    assert output["artifact"]["content"]["template_id"] == "recouvrement_reminder_short_v1"
    assert output["artifact"]["content"]["template_version"] == "1.0.0"
    assert output["artifact"]["content"]["template_label"] == "relance amiable"
    assert output["artifact"]["content"]["model_id"] is None
    assert output["artifact"]["content"]["prompt_version"] is None
    assert output["artifact"]["content"]["policy_review_status"] == "approved"
    message = str(output["artifact"]["content"]["message_client"])
    assert "Bonjour M. D." in message
    assert "840,00 €" in message
    assert "retard de 32 jours" in message
    assert "Cordialement" in message
    assert "mise en demeure" not in message.lower()
    assert output["cardUpdates"]["complianceChecks"] == [
        "Ton amiable et factuel",
        "Aucune menace ni pression injustifiée",
        "Aucun message envoyé",
        "Montant cohérent : 840,00 €",
        "Aucune validation d'échéancier requise dans ce brouillon",
    ]
    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["client_message_safety"]["score"] == 1.0
    assert scores["artifact_governance"]["score"] == 1.0
    assert scores["amount_consistency"]["score"] == 1.0
    assert scores["validation_required_compliance"]["status"] == "unknown"
    message_event = next(
        row for row in output["businessEvents"] if row["event_name"] == "message.generated"
    )
    assert message_event["artifact_id"] == "RC-2048-reminder-v1"
    assert message_event["artifact_type"] == "reminder_draft_v1"
    assert message_event["payload"]["generation_mode"] == "approved_template"
    assert message_event["payload"]["template_id"] == "recouvrement_reminder_short_v1"
    assert message_event["payload"]["policy_review_status"] == "approved"
    policy_event = next(
        row
        for row in output["businessEvents"]
        if row["event_name"] == "policy.decision_made"
        and row["payload"].get("policy_rule") == "recouvrement.client_message_safety"
    )
    assert policy_event["payload"]["amount_consistent"] is True


def test_recouvrement_graph_prepares_client_message_from_schedule_artifact(
    observed_recouvrement_stores: Path,
) -> None:
    schedule = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="ok puis-je lui proposer un étalement sur 36 mois ?",
        conversation_id="conv-rc-schedule-message",
        turn_id="turn-schedule-first",
        assistant_state={"activeTask": "propose_schedule"},
    )
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Prépare le message client",
        conversation_id="conv-rc-schedule-message",
        turn_id="turn-message-from-schedule",
        assistant_state={
            "activeTask": "draft_reminder",
            "currentArtifact": schedule["artifact"],
        },
    )

    assert output["decisions"]["intent"] == "draft_reminder"
    assert output["artifact"]["type"] == "client_message_artifact"
    assert output["artifact"]["content"]["validation_required"] is True
    assert output["artifact"]["content"]["client_agreement_required"] is True
    assert output["artifact"]["content"]["schedule_created"] is False
    assert output["artifact"]["content"]["message_sent"] is False
    assert output["artifact"]["content"]["generation_mode"] == "approved_template"
    assert output["artifact"]["content"]["template_id"] == "recouvrement_schedule_message_v1"
    assert output["artifact"]["content"]["policy_review_status"] == "validation_required"
    assert output["artifact"]["content"]["no_message_sent"] is True
    assert output["artifact"]["content"]["no_schedule_created"] is True
    message = str(output["artifact"]["content"]["message_client"])
    assert "36 mois" in message
    assert "23,33 €" in message
    assert "sous réserve de validation interne" in message
    assert "aucun échéancier créé" not in message.lower()
    assert output["cardUpdates"]["paymentPlan"] == [
        "Solution d'échelonnement évoquée uniquement comme option à valider",
        "Montant dû : 840,00 €",
        "Durée indicative : 36 mois",
        "Mensualité indicative : 23,33 €",
        "Échéancier non créé",
    ]
    assert "Aucun échéancier créé" in output["cardUpdates"]["complianceChecks"]
    assert any(row["event_name"] == "validation.requested" for row in output["businessEvents"])
    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["client_message_safety"]["score"] == 1.0
    assert scores["validation_required_compliance"]["score"] == 1.0
    assert scores["amount_consistency"]["score"] == 1.0
    message_event = next(
        row for row in output["businessEvents"] if row["event_name"] == "message.generated"
    )
    assert message_event["payload"]["generation_mode"] == "approved_template"
    assert message_event["payload"]["template_id"] == "recouvrement_schedule_message_v1"
    assert message_event["payload"]["policy_review_status"] == "validation_required"


def test_recouvrement_graph_updates_current_draft_with_empathic_tone(
    observed_recouvrement_stores: Path,
) -> None:
    first = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Rédiger une relance",
        conversation_id="conv-rc-empathy",
        turn_id="turn-draft-v1",
        assistant_state={"activeTask": "draft_reminder"},
    )
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="rends-le plus empathique",
        conversation_id="conv-rc-empathy",
        turn_id="turn-draft-v2",
        assistant_state={
            "activeTask": "draft_reminder",
            "currentArtifact": first["artifact"],
        },
    )

    assert output["artifact"]["type"] == "reminder_draft_v1"
    assert output["artifact"]["content"]["tone"] == "empathique"
    assert output["artifact"]["content"]["generation_mode"] == "approved_template"
    assert output["artifact"]["content"]["template_id"] == "recouvrement_reminder_empathic_v1"
    assert output["artifact"]["content"]["template_label"] == "ton plus empathique"
    assert output["cardUpdates"]["draftVersionLabel"] == ["Version 2 — ton plus empathique"]
    message = str(output["artifact"]["content"]["message_client"])
    assert "Nous comprenons" in message
    assert "RC-2048" in message
    assert "840,00 €" in message
    assert output["artifact"]["content"]["message_sent"] is False


def test_recouvrement_action_submits_schedule_for_validation_without_creation(
    observed_recouvrement_stores: Path,
) -> None:
    schedule = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="ok puis-je lui proposer un étalement sur 36 mois ?",
        conversation_id="conv-rc-action-validation",
        turn_id="turn-schedule-before-validation",
        assistant_state={"activeTask": "propose_schedule"},
    )

    output = run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact=schedule["artifact"],
        action_name="submit_for_validation",
        conversation_id="conv-rc-action-validation",
        turn_id="turn-submit-validation",
    )

    assert output["artifact"]["id"] == schedule["artifact"]["id"]
    assert output["artifact"]["type"] == "schedule_proposal_v2"
    assert output["artifact"]["status"] == "pending_validation"
    assert output["artifact"]["content"]["validation_status"] == "pending_validation"
    assert output["artifact"]["content"]["schedule_created"] is False
    assert output["artifact"]["content"]["no_schedule_created"] is True
    assert output["artifact"]["content"]["message_sent"] is False
    assert output["artifact"]["content"]["no_message_sent"] is True
    assert output["artifact"]["content"]["no_external_effect"] is True
    assert "Soumission à validation préparée" in output["visibleReply"]
    assert "Aucune action client n'a été exécutée" in output["visibleReply"]
    assert "Aucun échéancier créé" in output["cardUpdates"]["complianceChecks"]
    names = [row["event_name"] for row in output["businessEvents"]]
    assert names == [
        "case.context_loaded",
        "action.requested",
        "policy.decision_made",
        "validation.requested",
        "artifact.status_changed",
        "action.prepared",
        "message.generated",
    ]
    validation_event = next(
        row for row in output["businessEvents"] if row["event_name"] == "validation.requested"
    )
    assert validation_event["artifact_status"] == "pending_validation"
    assert validation_event["payload"]["no_external_effect"] is True
    action_event = next(
        row for row in output["businessEvents"] if row["event_name"] == "action.prepared"
    )
    assert action_event["payload"]["action_name"] == "submit_for_validation"
    assert action_event["payload"]["no_external_effect"] is True
    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["action_governance"]["score"] == 1.0
    assert scores["no_uncontrolled_external_effect"]["score"] == 1.0
    assert scores["validation_required_compliance"]["score"] == 1.0


def test_recouvrement_action_prepares_insertion_without_new_draft(
    observed_recouvrement_stores: Path,
) -> None:
    draft = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Rédiger une relance",
        conversation_id="conv-rc-action-insert",
        turn_id="turn-draft-before-insert",
        assistant_state={"activeTask": "draft_reminder"},
    )

    output = run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact=draft["artifact"],
        action_name="insert_artifact_in_case",
        conversation_id="conv-rc-action-insert",
        turn_id="turn-insert",
    )

    assert output["artifact"]["id"] == draft["artifact"]["id"]
    assert output["artifact"]["type"] == "reminder_draft_v1"
    assert output["artifact"]["status"] == "insertion_prepared"
    assert output["artifact"]["content"]["message_client"] == draft["artifact"]["content"][
        "message_client"
    ]
    assert output["artifact"]["content"]["insertion_executed"] is False
    assert output["artifact"]["content"]["case_write_executed"] is False
    assert output["artifact"]["content"]["message_sent"] is False
    assert output["artifact"]["content"]["no_external_effect"] is True
    assert "Insertion préparée" in output["visibleReply"]
    assert "Aucune écriture définitive" in output["visibleReply"]
    assert not any(row["event_name"] == "validation.requested" for row in output["businessEvents"])
    assert any(
        row["event_name"] == "artifact.status_changed"
        and row["artifact_status"] == "insertion_prepared"
        for row in output["businessEvents"]
    )
    assert not any(
        row["event_name"] == "artifact.created"
        and row["artifact_type"] == "reminder_draft_v1"
        for row in output["businessEvents"]
    )
    assert "Aucun nouveau brouillon généré" in output["cardUpdates"]["complianceChecks"]


def test_recouvrement_action_prepares_tomorrow_reminder_for_blocked_contact(
    observed_recouvrement_stores: Path,
) -> None:
    contact = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 23h ?",
        conversation_id="conv-rc-action-reminder",
        turn_id="turn-contact-before-reminder",
    )

    output = run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact=contact["artifact"],
        action_name="prepare_reminder_tomorrow",
        conversation_id="conv-rc-action-reminder",
        turn_id="turn-reminder-tomorrow",
    )

    assert output["artifact"]["type"] == "contact_rule_v1"
    assert output["artifact"]["status"] == "reminder_prepared"
    assert output["artifact"]["content"]["calendar_event_created"] is False
    assert output["artifact"]["content"]["no_external_effect"] is True
    assert "Aucun événement calendrier réel n'a été créé" in output["visibleReply"]
    assert any(
        row["event_name"] == "action.prepared"
        and row["payload"]["action_name"] == "prepare_reminder_tomorrow"
        for row in output["businessEvents"]
    )
    scores = {row["metric"]: row for row in output["businessScores"]}
    assert scores["no_uncontrolled_external_effect"]["score"] == 1.0


def test_recouvrement_action_denies_unauthorized_surface(
    observed_recouvrement_stores: Path,
) -> None:
    schedule = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Peut-on étaler sur 36 mois ?",
        conversation_id="conv-rc-action-deny-source",
        turn_id="turn-schedule-source",
    )

    output = run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact=schedule["artifact"],
        action_name="submit_for_validation",
        conversation_id="conv-rc-action-deny",
        turn_id="turn-action-deny",
        surface="public",
    )

    assert output["artifact"]["type"] == "authorization_denial_v1"
    assert output["artifact"]["status"] == "blocked"
    assert output["decisions"]["authorization"]["reason_codes"] == ["UNAUTHORIZED_SURFACE"]
    assert [row["event_name"] for row in output["businessEvents"]] == ["action.blocked"]
    assert output["businessEvents"][0]["payload"]["action_name"] == "submit_for_validation"
    assert output["businessEvents"][0]["payload"]["no_external_effect"] is True


def test_recouvrement_message_templates_are_not_scattered_in_graph() -> None:
    graph_source = Path("src/tessera/agent/recouvrement.py").read_text(encoding="utf-8")
    template_source = Path("src/tessera/recouvrement/message_templates.py").read_text(
        encoding="utf-8"
    )

    assert (
        "Nous comprenons que votre situation puisse nécessiter un échange adapté."
        not in graph_source
    )
    assert "Nous vous contactons au sujet du dossier" not in graph_source
    assert "Cordialement" not in graph_source
    assert "recouvrement_reminder_short_v1" in template_source
    assert "recouvrement_reminder_empathic_v1" in template_source
    assert "recouvrement_schedule_message_v1" in template_source


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
        "client_message_safety",
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


async def test_recouvrement_assistant_endpoint_returns_schedule_contract(
    observed_recouvrement_stores: Path,
) -> None:
    payload = RecouvrementAssistantRequest(
        case_id="RC-2048",
        message="ok puis-je lui proposer un étalement sur 36 mois ?",
        conversation_id="conv-rc-endpoint-schedule",
        turn_id="turn-endpoint-schedule",
        assistant_state={"activeTask": "check_rule"},
    )
    output = await recouvrement_assistant_message(payload)

    assert output["decisions"]["intent"] == "propose_schedule"
    assert output["artifact"]["type"] == "schedule_proposal_v2"
    assert output["artifact"]["content"]["monthly_amount"] == "23,33 €"
    assert output["artifact"]["content"]["schedule_created"] is False
    assert "validation requise" in "\n".join(output["cardUpdates"]["complianceChecks"]).lower()
    assert {row["event_name"] for row in output["businessEvents"]} >= {
        "intent.routed",
        "slots.extracted",
        "business_rule.checked",
        "artifact.created",
        "validation.requested",
        "action.prepared",
        "message.generated",
    }


async def test_recouvrement_assistant_endpoint_returns_draft_contract(
    observed_recouvrement_stores: Path,
) -> None:
    payload = RecouvrementAssistantRequest(
        case_id="RC-2048",
        message="Rédiger une relance",
        conversation_id="conv-rc-endpoint-draft",
        turn_id="turn-endpoint-draft",
        assistant_state={"activeTask": "draft_reminder"},
    )
    output = await recouvrement_assistant_message(payload)

    assert output["decisions"]["intent"] == "draft_reminder"
    assert output["artifact"]["type"] == "reminder_draft_v1"
    assert output["artifact"]["content"]["message_sent"] is False
    assert output["artifact"]["content"]["schedule_created"] is False
    assert "Aucun message envoyé" in output["cardUpdates"]["complianceChecks"]
    assert {row["event_name"] for row in output["businessEvents"]} >= {
        "intent.routed",
        "slots.extracted",
        "policy.decision_made",
        "artifact.created",
        "action.prepared",
        "message.generated",
    }


async def test_recouvrement_assistant_endpoint_returns_summary_contract(
    observed_recouvrement_stores: Path,
) -> None:
    payload = RecouvrementAssistantRequest(
        case_id="RC-2048",
        message="Résumer ce dossier",
        conversation_id="conv-rc-endpoint-summary",
        turn_id="turn-endpoint-summary",
        assistant_state={"activeTask": "summary"},
    )
    output = await recouvrement_assistant_message(payload)

    assert output["decisions"]["intent"] == "summarize_case"
    assert output["artifact"]["type"] == "case_summary_v1"
    assert output["artifact"]["content"]["amount_due"] == "840,00 €"
    assert output["artifact"]["content"]["days_late"] == 32
    assert output["artifact"]["content"]["no_external_effect"] is True
    assert "Aucun message client généré" in output["cardUpdates"]["complianceChecks"]
    assert output["suggestedActions"] == [
        "Rédiger une relance",
        "Vérifier une règle",
        "Proposer un échéancier",
        "Insérer dans le dossier",
    ]


async def test_recouvrement_assistant_action_endpoint_returns_governed_action_contract(
    observed_recouvrement_stores: Path,
) -> None:
    draft = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Rédiger une relance",
        conversation_id="conv-rc-action-endpoint-source",
        turn_id="turn-action-endpoint-source",
        assistant_state={"activeTask": "draft_reminder"},
    )
    payload = RecouvrementAssistantActionRequest(
        case_id="RC-2048",
        artifact=draft["artifact"],
        action_name="insert_artifact_in_case",
        conversation_id="conv-rc-action-endpoint",
        turn_id="turn-action-endpoint",
    )
    output = await recouvrement_assistant_action(payload)

    assert output["artifact"]["type"] == "reminder_draft_v1"
    assert output["artifact"]["status"] == "insertion_prepared"
    assert output["artifact"]["content"]["case_write_executed"] is False
    assert output["artifact"]["content"]["no_external_effect"] is True
    assert "Aucune écriture définitive" in output["visibleReply"]
    assert {row["event_name"] for row in output["businessEvents"]} >= {
        "action.requested",
        "policy.decision_made",
        "artifact.status_changed",
        "action.prepared",
        "message.generated",
    }


async def test_observability_recouvrement_runs_groups_turns_artifacts_actions_and_scores(
    observed_recouvrement_stores: Path,
) -> None:
    summary = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Résumer ce dossier",
        conversation_id="conv-rc-cockpit",
        turn_id="turn-summary",
        assistant_state={"activeTask": "summary"},
    )
    contact = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Je peux l'appeler à 23h ?",
        conversation_id="conv-rc-cockpit",
        turn_id="turn-contact-blocked",
    )
    schedule = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="ok puis-je lui proposer un étalement sur 36 mois ?",
        conversation_id="conv-rc-cockpit",
        turn_id="turn-schedule-36",
        assistant_state={"activeTask": "propose_schedule"},
    )
    message = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Prépare le message client",
        conversation_id="conv-rc-cockpit",
        turn_id="turn-client-message",
        assistant_state={
            "activeTask": "draft_reminder",
            "currentArtifact": schedule["artifact"],
        },
    )
    validation = run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact=schedule["artifact"],
        action_name="submit_for_validation",
        conversation_id="conv-rc-cockpit",
        turn_id="turn-submit-validation",
    )
    insertion = run_recouvrement_action_workflow_v1(
        case_id="RC-2048",
        artifact=message["artifact"],
        action_name="insert_artifact_in_case",
        conversation_id="conv-rc-cockpit",
        turn_id="turn-insertion-prepared",
    )

    payload = await obs.observability_recouvrement_runs(conversation_id="conv-rc-cockpit")
    runs = {run["turn_id"]: run for run in payload["runs"]}

    assert set(runs) == {
        "turn-summary",
        "turn-contact-blocked",
        "turn-schedule-36",
        "turn-client-message",
        "turn-submit-validation",
        "turn-insertion-prepared",
    }
    assert runs["turn-contact-blocked"]["agent_id"] == RECOUVREMENT_AGENT_ID
    assert runs["turn-contact-blocked"]["workflow_id"] == RECOUVREMENT_WORKFLOW_ID
    assert any(
        decision["decision"] == "blocked"
        and "OUTSIDE_CONTACT_WINDOW" in decision["reason_codes"]
        for decision in runs["turn-contact-blocked"]["decisions"]
    )

    summary_artifact = runs["turn-summary"]["artifacts"][0]
    assert summary_artifact["artifact_type"] == "case_summary_v1"
    assert summary_artifact["no_external_effect"] is True
    summary_scores = {score["metric"]: score for score in runs["turn-summary"]["scores"]}
    assert summary_scores["no_uncontrolled_external_effect"]["score"] == 1.0

    schedule_artifact = runs["turn-schedule-36"]["artifacts"][0]
    assert schedule_artifact["artifact_type"] == "schedule_proposal_v2"
    assert schedule_artifact["no_schedule_created"] is True

    message_artifact = runs["turn-client-message"]["artifacts"][0]
    assert message_artifact["artifact_type"] == "client_message_artifact"
    assert message_artifact["generation_mode"] == "approved_template"
    assert message_artifact["template_id"] == "recouvrement_schedule_message_v1"
    assert message_artifact["no_message_sent"] is True
    assert message_artifact["no_schedule_created"] is True

    validation_action = runs["turn-submit-validation"]["sensitive_actions"]
    assert any(
        action["action_name"] == "submit_for_validation"
        and action["target_status"] == "pending_validation"
        and action["no_external_effect"] is True
        for action in validation_action
    )
    insertion_action = runs["turn-insertion-prepared"]["sensitive_actions"]
    assert any(
        action["action_name"] == "insert_artifact_in_case"
        and action["target_status"] == "insertion_prepared"
        and action["no_external_effect"] is True
        for action in insertion_action
    )
    validation_scores = {
        score["metric"]: score for score in runs["turn-submit-validation"]["scores"]
    }
    assert validation_scores["validation_required_compliance"]["score"] == 1.0
    assert validation_scores["no_uncontrolled_external_effect"]["score"] == 1.0

    assert validation["artifact"]["status"] == "pending_validation"
    assert insertion["artifact"]["status"] == "insertion_prepared"
    assert summary["artifact"]["type"] == "case_summary_v1"
    assert contact["artifact"]["content"]["decision"] == "blocked"

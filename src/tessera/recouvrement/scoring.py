"""Business scores for the Recouvrement collections workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tessera.observability.business_events import BusinessEventName
from tessera.observability.business_scoring import BusinessScore, register_business_scorer

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

__all__ = [
    "RECOUVREMENT_WORKFLOW_ID",
    "RecouvrementBusinessScorer",
    "ensure_recouvrement_scorer_registered",
    "score_recouvrement_events",
]

RECOUVREMENT_AGENT_ID: Final = "recouvrement"
RECOUVREMENT_WORKFLOW_ID: Final = "recouvrement_collections_v1"
_SCORER_ID: Final = "recouvrement.collections.v1"

_SENSITIVE_ARTIFACTS: Final = {
    "contact_rule",
    "contact_rule_v1",
    "schedule_proposal",
    "schedule_proposal_v2",
    "client_message_artifact",
    "reminder_draft_v1",
}
_SENSITIVE_ACTIONS: Final = {
    "prepare_outbound_call",
    "create_schedule",
    "submit_schedule",
    "send_client_message",
}


def _rows(events: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    return [dict(event) for event in events]


def _is_recouvrement(rows: list[dict[str, object]]) -> bool:
    return any(
        row.get("agent_id") == RECOUVREMENT_AGENT_ID
        or row.get("workflow_id") == RECOUVREMENT_WORKFLOW_ID
        for row in rows
    )


def _names(rows: list[dict[str, object]]) -> set[str]:
    return {str(row.get("event_name", "")) for row in rows}


def _reason_codes(row: Mapping[str, object]) -> set[str]:
    raw = row.get("reason_codes")
    return {str(code) for code in raw} if isinstance(raw, list) else set()


def _payload(row: Mapping[str, object]) -> Mapping[str, object]:
    raw = row.get("payload")
    return raw if isinstance(raw, dict) else {}


def _action_name(row: Mapping[str, object]) -> str:
    payload = _payload(row)
    return str(
        payload.get("action_name") or payload.get("action") or payload.get("action_id") or ""
    )


def _unknown(metric: str, reason: str) -> BusinessScore:
    return BusinessScore(metric=metric, score=None, status="unknown", reason=reason)


def _not_applicable(metric: str, reason: str) -> BusinessScore:
    return BusinessScore(metric=metric, score=None, status="not_applicable", reason=reason)


def _scored(metric: str, score: float, reason: str) -> BusinessScore:
    return BusinessScore(metric=metric, score=score, status="scored", reason=reason)


def _contact_window_compliance(rows: list[dict[str, object]]) -> BusinessScore:
    checks = [
        row
        for row in rows
        if row.get("event_name") == BusinessEventName.BUSINESS_RULE_CHECKED.value
        and (
            _payload(row).get("rule_id") == "CONTACT_WINDOW"
            or "OUTSIDE_CONTACT_WINDOW" in _reason_codes(row)
            or "UNAUTHORIZED_SURFACE" in _reason_codes(row)
        )
    ]
    if not checks:
        return _not_applicable("contact_window_compliance", "no_contact_window_event")
    if any("UNAUTHORIZED_SURFACE" in _reason_codes(row) for row in checks):
        return _not_applicable("contact_window_compliance", "authorization_blocked_before_rule")
    if any(row.get("decision") == "blocked" for row in checks):
        return _scored("contact_window_compliance", 1.0, "outside_contact_window_blocked")
    if any("OUTSIDE_CONTACT_WINDOW" in _reason_codes(row) for row in checks):
        return _scored("contact_window_compliance", 0.0, "outside_contact_window_not_blocked")
    return _unknown("contact_window_compliance", "contact_window_event_not_decisive")


def _action_blocking_correctness(rows: list[dict[str, object]]) -> BusinessScore:
    blocked = [
        row
        for row in rows
        if row.get("event_name") == BusinessEventName.ACTION_BLOCKED.value
        and bool(_reason_codes(row))
    ]
    if blocked:
        return _scored("action_blocking_correctness", 1.0, "sensitive_action_blocked")
    prepared_sensitive = [
        row
        for row in rows
        if row.get("event_name") == BusinessEventName.ACTION_PREPARED.value
        and _action_name(row) in _SENSITIVE_ACTIONS
    ]
    if prepared_sensitive:
        return _scored(
            "action_blocking_correctness",
            0.0,
            "sensitive_action_prepared_without_explicit_block",
        )
    return _not_applicable("action_blocking_correctness", "no_sensitive_action_event")


def _artifact_governance(rows: list[dict[str, object]]) -> BusinessScore:
    artifacts = [
        row
        for row in rows
        if row.get("event_name") == BusinessEventName.ARTIFACT_CREATED.value
        and str(row.get("artifact_type") or "") in _SENSITIVE_ARTIFACTS
    ]
    if not artifacts:
        return _not_applicable("artifact_governance", "no_sensitive_artifact_created")
    required = ("artifact_type", "artifact_status", "case_id", "agent_id", "workflow_id")
    if all(all(row.get(field) for field in required) for row in artifacts):
        return _scored("artifact_governance", 1.0, "sensitive_artifacts_traceable")
    return _scored("artifact_governance", 0.0, "sensitive_artifact_missing_traceability")


def _validation_required_compliance(rows: list[dict[str, object]]) -> BusinessScore:
    validation_requested = any(
        row.get("event_name") == BusinessEventName.VALIDATION_REQUESTED.value for row in rows
    )
    pending_validation = any(row.get("artifact_status") == "pending_validation" for row in rows)
    if validation_requested or pending_validation:
        return _scored("validation_required_compliance", 1.0, "validation_requested_or_pending")
    sensitive_inserted = any(
        row.get("artifact_status") in {"inserted", "executed"}
        and str(row.get("artifact_type") or "") in _SENSITIVE_ARTIFACTS
        for row in rows
    )
    if sensitive_inserted:
        return _scored(
            "validation_required_compliance",
            0.0,
            "sensitive_artifact_inserted_without_validation",
        )
    return _unknown("validation_required_compliance", "no_validation_required_event")


def _trace_completeness(rows: list[dict[str, object]]) -> BusinessScore:
    names = _names(rows)
    if BusinessEventName.ACTION_BLOCKED.value in names and "case.context_loaded" not in names:
        return _not_applicable("recouvrement_trace_completeness", "blocked_before_case_context")
    expected = {
        BusinessEventName.INTENT_ROUTED.value,
        BusinessEventName.SLOTS_EXTRACTED.value,
        BusinessEventName.BUSINESS_RULE_CHECKED.value,
        BusinessEventName.MESSAGE_GENERATED.value,
    }
    has_policy_equivalent = BusinessEventName.POLICY_DECISION_MADE.value in names or any(
        row.get("event_name") == BusinessEventName.BUSINESS_RULE_CHECKED.value
        and row.get("decision")
        for row in rows
    )
    expected.add(BusinessEventName.POLICY_DECISION_MADE.value)
    if any(row.get("artifact_id") or row.get("artifact_type") for row in rows):
        expected.add(BusinessEventName.ARTIFACT_CREATED.value)
    if any(row.get("event_name") in {"action.blocked", "action.prepared"} for row in rows):
        expected.add("action.blocked_or_prepared")
    present = set(names)
    if has_policy_equivalent:
        present.add(BusinessEventName.POLICY_DECISION_MADE.value)
    if (
        BusinessEventName.ACTION_BLOCKED.value in names
        or BusinessEventName.ACTION_PREPARED.value in names
    ):
        present.add("action.blocked_or_prepared")
    score = len(expected & present) / len(expected) if expected else 0.0
    return _scored("recouvrement_trace_completeness", score, "expected_events_present_ratio")


def _amount_consistency(rows: list[dict[str, object]]) -> BusinessScore:
    schedule_events = [
        row for row in rows if str(row.get("artifact_type") or "").startswith("schedule")
    ]
    if not schedule_events:
        return _unknown("amount_consistency", "not_enough_schedule_amount_data")
    amounts = {
        str(_payload(row).get("amount_due"))
        for row in schedule_events
        if _payload(row).get("amount_due") is not None
    }
    if len(amounts) <= 1:
        return _scored("amount_consistency", 1.0, "amount_fields_consistent")
    return _scored("amount_consistency", 0.0, "amount_fields_conflict")


class RecouvrementBusinessScorer:
    """Scores Recouvrement collections workflow events."""

    scorer_id = _SCORER_ID

    def supports(self, events: Iterable[Mapping[str, object]]) -> bool:
        """Only Recouvrement workflow rows are scored by this scorer."""
        return _is_recouvrement(_rows(events))

    def score(self, events: Iterable[Mapping[str, object]]) -> list[BusinessScore]:
        """Return the Recouvrement v1 deterministic score set."""
        rows = _rows(events)
        if not rows or not _is_recouvrement(rows):
            return []
        return [
            _contact_window_compliance(rows),
            _action_blocking_correctness(rows),
            _artifact_governance(rows),
            _validation_required_compliance(rows),
            _trace_completeness(rows),
            _amount_consistency(rows),
        ]


def score_recouvrement_events(events: Iterable[Mapping[str, object]]) -> list[BusinessScore]:
    """Score Recouvrement rows directly; primarily useful for focused tests."""
    return RecouvrementBusinessScorer().score(events)


_REGISTERED = False


def ensure_recouvrement_scorer_registered() -> None:
    """Register the Recouvrement scorer with the generic business scoring registry."""
    global _REGISTERED
    if _REGISTERED:
        return
    register_business_scorer(RecouvrementBusinessScorer())
    _REGISTERED = True

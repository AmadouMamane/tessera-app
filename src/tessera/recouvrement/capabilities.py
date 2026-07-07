"""Recouvrement capability attribution (ADR 0017 §A1.1/A1.2).

The mapping from drawer/runtime task names to manifest capability ids is domain-owned:
observability reads the stamped ``capability_id`` but never guesses it from payloads.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "capability_for_action",
    "capability_for_artifact_type",
    "capability_for_task",
]

_TASK_TO_CAPABILITY: Final[dict[str, str]] = {
    "summary": "summarize_case",
    "summarize_case": "summarize_case",
    "check_rule": "check_contact_rule",
    "check_contact_rule": "check_contact_rule",
    "explain_payment_options": "explain_payment_options",
    "draft_reminder": "draft_reminder",
    "propose_schedule": "propose_schedule",
}

_ARTIFACT_TYPE_TO_CAPABILITY: Final[dict[str, str]] = {
    "case_summary_v1": "summarize_case",
    "contact_rule_v1": "check_contact_rule",
    "payment_options_v1": "explain_payment_options",
    "reminder_draft_v1": "draft_reminder",
    "client_message_artifact": "draft_reminder",
    "schedule_proposal_v2": "propose_schedule",
}

_ACTION_TO_CAPABILITY: Final[dict[str, str]] = {
    "prepare_schedule_proposal": "propose_schedule",
    "prepare_client_message": "draft_reminder",
    "prepare_outbound_call": "check_contact_rule",
    "prepare_reminder_tomorrow": "check_contact_rule",
}


def capability_for_task(task: object) -> str | None:
    """Return the manifest capability id for a runtime task/intent, if declared."""
    if not isinstance(task, str):
        return None
    return _TASK_TO_CAPABILITY.get(task)


def capability_for_artifact_type(artifact_type: object) -> str | None:
    """Return the manifest capability id for a Recouvrement artifact type, if declared."""
    if not isinstance(artifact_type, str):
        return None
    return _ARTIFACT_TYPE_TO_CAPABILITY.get(artifact_type)


def capability_for_action(action_name: object) -> str | None:
    """Return the manifest capability id for a Recouvrement action, if declared."""
    if not isinstance(action_name, str):
        return None
    return _ACTION_TO_CAPABILITY.get(action_name)

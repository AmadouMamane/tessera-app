"""End-to-end locale contract for the structured Recouvrement experience."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import pytest

from tessera.agent.recouvrement import (
    run_recouvrement_action_workflow_v1,
    run_recouvrement_graph_v1,
)
from tessera.authz import Actor

if TYPE_CHECKING:
    from tessera.recouvrement.message_templates import RecouvrementLanguage

_PROMPTS = (
    "Summarize this case.",
    "What payment options are available?",
    "Prepare a 3 month payment plan.",
    "Write a customer reminder.",
    # BOTH branches of the contact rule. Only the refused one used to be exercised, and the
    # ALLOWED one leaked three French strings into English and German for as long as it had
    # existed: a translation table is only as complete as the branches somebody walked.
    "May I call the customer at 22:00?",
    "May I call the customer at 10:00?",
)

_FRENCH_UI_WORDS = re.compile(
    r"\b(?:dossier|montant|retard|promesse|aucun|aucune|échéancier|échelonnement|"
    r"paiement|relance|règle|autorisé|préparé|conseillé|mensualités|mois|"
    r"soumettre|vérifier|rédiger|insérer|plage|appel|écriture)\b",
    re.IGNORECASE,
)


def _ui_strings(output: dict[str, object]) -> list[str]:
    """Collect the text the drawer can render, excluding canonical machine metadata."""
    strings = [str(output["visibleReply"])]
    artifact = output["artifact"]
    assert isinstance(artifact, dict)
    strings.append(str(artifact["title"]))
    ignored_content_keys = {
        "case_id",
        "client",
        "decision",
        "generation_mode",
        "model_id",
        "policy_review_status",
        "prompt_version",
        "reason_codes",
        "source_artifact_id",
        "template_id",
        "template_version",
    }

    def collect(value: Any) -> None:
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in ignored_content_keys:
                    collect(item)

    collect(artifact.get("content", {}))
    collect(output["cardUpdates"])
    collect(output["suggestedActions"])
    return strings


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("prompt", _PROMPTS)
def test_structured_recouvrement_user_copy_is_localized(
    language: RecouvrementLanguage,
    prompt: str,
) -> None:
    output = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message=prompt,
        language=language,
    )
    leaking = sorted({text for text in _ui_strings(output) if _FRENCH_UI_WORDS.search(text)})
    assert leaking == []


def test_multilingual_intent_router_understands_native_operator_phrasing() -> None:
    english = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Prepare a 6 month payment plan.",
        language="en",
    )
    german = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message="Bitte einen Ratenplan über 6 Monate vorbereiten.",
        language="de",
    )
    assert english["decisions"]["intent"] == "propose_schedule"  # type: ignore[index]
    assert german["decisions"]["intent"] == "propose_schedule"  # type: ignore[index]
    assert english["artifact"]["content"]["duration_months"] == 6
    assert german["artifact"]["content"]["duration_months"] == 6


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    ("prompt", "action_name", "surface"),
    [
        ("Prepare a 3 month payment plan.", "submit_for_validation", "dedicated-ui"),
        ("Write a customer reminder.", "insert_artifact_in_case", "dedicated-ui"),
        ("May I call the customer at 22:00?", "prepare_reminder_tomorrow", "dedicated-ui"),
        ("Prepare a 3 month payment plan.", "submit_for_validation", "public"),
    ],
)
def test_structured_recouvrement_actions_and_denials_are_localized(
    language: RecouvrementLanguage,
    prompt: str,
    action_name: str,
    surface: str,
) -> None:
    source = run_recouvrement_graph_v1(
        case_id="RC-2048",
        message=prompt,
        language=language,
    )
    output = run_recouvrement_action_workflow_v1(
        actor=Actor(principal="i18n.operator@credit-aurore.eu", role="collections"),
        case_id="RC-2048",
        artifact=source["artifact"],
        action_name=action_name,
        surface=surface,
        language=language,
    )
    leaking = sorted({text for text in _ui_strings(output) if _FRENCH_UI_WORDS.search(text)})
    assert leaking == []

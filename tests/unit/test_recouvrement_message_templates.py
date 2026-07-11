"""Closure tests for the fabricated payment-promise date.

Audit 2026-07-10, P0 ``fabricated-regulated-output``:
``src/tessera/recouvrement/message_templates.py:56, :76, :95`` hardcoded the
sentence "Votre promesse de paiement du 12 juin n'a pas pu être tenue" into three
approved dunning templates. Only ``{days_late}`` was a field, so every letter
asserted a specific broken promise that was never read from the case file — a
fabricated financial claim inside a regulated artifact.

Each test below fails against the pre-fix templates: the first two because the
clause was a constant that no case data could remove or move, the third because
the sentence was present regardless of the file's contents.
"""

from __future__ import annotations

from datetime import date

import pytest

from tessera.agent.recouvrement import RecouvrementCaseSnapshot, draft_client_message
from tessera.recouvrement.message_templates import (
    RECOUVREMENT_MESSAGE_TEMPLATES,
    format_promise_date,
    render_missed_promise_clause,
)

PROMISE_TEMPLATE_IDS = (
    "recouvrement_reminder_short_v1",
    "recouvrement_reminder_empathic_v1",
    "recouvrement_schedule_message_v1",
)


def _case(missed_promise_date: date | None) -> RecouvrementCaseSnapshot:
    """Build a case snapshot that differs from RC-2048 only by its promise date."""
    return RecouvrementCaseSnapshot(
        case_id="RC-9001",
        client="Mme R.",
        amount_due_label="1 240,00 €",
        amount_due=1240.0,
        days_late=17,
        contact_window_start="09:00",
        contact_window_end="18:00",
        recommended_channel="email",
        alternative_channel="appel sortant",
        missed_promise_date=missed_promise_date,
    )


def _draft(case: RecouvrementCaseSnapshot, slots: dict[str, object] | None = None) -> str:
    state = {"case": case, "slots": slots or {}}
    return str(draft_client_message(state)["draft_message"])  # type: ignore[arg-type]


def test_clause_omitted_when_the_file_records_no_promise() -> None:
    """No promise on file means no promise clause — not a defaulted one."""
    assert render_missed_promise_clause(None) == ""


def test_clause_carries_the_date_from_the_file() -> None:
    """The clause states the case's own date, not a constant."""
    clause = render_missed_promise_clause(date(2026, 5, 3))
    assert "3 mai" in clause
    assert "12 juin" not in clause


@pytest.mark.parametrize("template_id", PROMISE_TEMPLATE_IDS)
def test_template_never_asserts_a_promise_absent_from_the_file(template_id: str) -> None:
    """A letter for a case with no recorded promise must not mention one at all."""
    rendered = RECOUVREMENT_MESSAGE_TEMPLATES[template_id].render(
        {
            "client": "Mme R.",
            "case_id": "RC-9001",
            "amount_due_label": "1 240,00 €",
            "days_late": 17,
            "missed_promise_clause": render_missed_promise_clause(None),
            "schedule_sentence": "",
        }
    )
    assert "promesse de paiement" not in rendered
    # The lateness is real case data and must survive the omission.
    assert "retard de 17 jours" in rendered


@pytest.mark.parametrize("template_id", PROMISE_TEMPLATE_IDS)
def test_template_states_the_promise_date_from_the_file(template_id: str) -> None:
    """A letter for a case with a recorded promise must state that case's date."""
    rendered = RECOUVREMENT_MESSAGE_TEMPLATES[template_id].render(
        {
            "client": "Mme R.",
            "case_id": "RC-9001",
            "amount_due_label": "1 240,00 €",
            "days_late": 17,
            "missed_promise_clause": render_missed_promise_clause(date(2026, 5, 3)),
            "schedule_sentence": "",
        }
    )
    assert "Votre promesse de paiement du 3 mai n'a pas pu être tenue." in rendered
    assert "12 juin" not in rendered


def test_drafted_letter_omits_the_clause_for_a_case_without_a_promise() -> None:
    """End to end through the drafting node: no promise on file, no claim in the letter."""
    draft = _draft(_case(None))
    assert "promesse de paiement" not in draft
    assert "retard de 17 jours" in draft


def test_drafted_letter_sources_the_promise_date_from_the_case() -> None:
    """End to end through the drafting node: the date comes from the case, not a constant."""
    draft = _draft(_case(date(2026, 5, 3)))
    assert "Votre promesse de paiement du 3 mai n'a pas pu être tenue." in draft
    assert "12 juin" not in draft


def test_schedule_template_still_carries_the_promise_clause() -> None:
    """The schedule-aware template is one of the three that must be sourced too."""
    draft = _draft(_case(date(2026, 5, 3)), {"mentions_schedule": True})
    assert "Votre promesse de paiement du 3 mai" in draft
    assert "échelonnement" in draft


def test_missed_promise_label_is_derived_from_the_date() -> None:
    """No surface may assert a promise the case file does not carry."""
    assert _case(None).missed_promise_label is None
    assert _case(date(2026, 6, 12)).missed_promise_label == (
        "promesse de paiement non tenue le 12 juin"
    )


@pytest.mark.parametrize(
    ("promise_date", "expected"),
    [
        (date(2026, 6, 12), "12 juin"),
        (date(2026, 6, 1), "1er juin"),
        (date(2026, 1, 31), "31 janvier"),
        (date(2026, 8, 9), "9 août"),
        (date(2026, 12, 25), "25 décembre"),
    ],
)
def test_promise_date_is_formatted_in_french_without_a_host_locale(
    promise_date: date, expected: str
) -> None:
    """A regulated letter must not depend on the container's locale database."""
    assert format_promise_date(promise_date) == expected

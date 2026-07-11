"""Approved message templates for the Recouvrement workflow."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from datetime import date

# Month names are spelled out rather than obtained from ``strftime``: locale
# availability is not guaranteed in the container, and a regulated letter must
# not depend on the host's locale database.
_FRENCH_MONTHS: Final = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)

GenerationMode = Literal[
    "approved_template",
    "deterministic_builder",
    "llm_generated",
    "llm_rewrite",
]


@dataclass(frozen=True, slots=True)
class RecouvrementMessageTemplate:
    """Versioned template approved for Recouvrement client-message drafting."""

    template_id: str
    template_version: str
    template_label: str
    template_tone: str
    template_body: str
    allowed_use_cases: tuple[str, ...]
    generation_mode: GenerationMode = "approved_template"
    prompt_version: str | None = None
    model_id: str | None = None

    def render(self, context: dict[str, object]) -> str:
        """Render the template with a bounded explicit context."""
        safe_context = {key: str(value) for key, value in context.items()}
        required_fields = {
            field_name
            for _, field_name, _, _ in Formatter().parse(self.template_body)
            if field_name is not None
        }
        missing = sorted(required_fields.difference(safe_context))
        if missing:
            missing_list = ", ".join(missing)
            raise ValueError(f"missing recouvrement template fields: {missing_list}")
        return self.template_body.format_map(safe_context)


def format_promise_date(promise_date: date) -> str:
    """Format a payment-promise date in French long form (``12 juin``, ``1er juin``)."""
    day = "1er" if promise_date.day == 1 else str(promise_date.day)
    return f"{day} {_FRENCH_MONTHS[promise_date.month - 1]}"


def render_missed_promise_clause(missed_promise_date: date | None) -> str:
    """Render the broken-promise clause, or nothing when the file records no promise.

    A dunning letter is a regulated artifact: it may only assert a broken payment
    promise when the case file actually carries one. When ``missed_promise_date``
    is ``None`` the clause is omitted entirely rather than defaulted.

    Args:
        missed_promise_date: Date of the broken promise as recorded on the case,
            or ``None`` when the file records none.

    Returns:
        The clause, ending with a separating space, or an empty string.
    """
    if missed_promise_date is None:
        return ""
    promise_day = format_promise_date(missed_promise_date)
    return f"Votre promesse de paiement du {promise_day} n'a pas pu être tenue. "


RECOUVREMENT_REMINDER_SHORT_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_reminder_short_v1",
    template_version="1.0.0",
    template_label="relance amiable",
    template_tone="amiable et factuel",
    allowed_use_cases=("draft_reminder",),
    template_body=(
        "Bonjour {client},\n\n"
        "Nous vous contactons au sujet du dossier {case_id}. Sauf erreur de notre part, "
        "le montant restant dû est de {amount_due_label}.\n\n"
        "{missed_promise_clause}Le dossier présente un retard de {days_late} jours.\n\n"
        "Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée "
        "à votre situation.\n\n"
        "Cordialement,\n"
        "Crédit Aurore"
    ),
)

RECOUVREMENT_REMINDER_EMPATHIC_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_reminder_empathic_v1",
    template_version="1.0.0",
    template_label="ton plus empathique",
    template_tone="empathique",
    allowed_use_cases=("draft_reminder", "rewrite_tone"),
    template_body=(
        "Bonjour {client},\n\n"
        "Nous comprenons que votre situation puisse nécessiter un échange adapté. "
        "Nous souhaitons faire le point avec vous concernant le dossier {case_id}, "
        "pour un montant restant dû de {amount_due_label}.\n\n"
        "{missed_promise_clause}Le dossier présente un retard de {days_late} jours.\n\n"
        "Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée "
        "à votre situation.\n\n"
        "Cordialement,\n"
        "Crédit Aurore"
    ),
)

RECOUVREMENT_SCHEDULE_MESSAGE_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_schedule_message_v1",
    template_version="1.0.0",
    template_label="Message client avec option d'échelonnement",
    template_tone="prudent et factuel",
    allowed_use_cases=("draft_reminder", "prepare_client_message", "propose_schedule"),
    template_body=(
        "Bonjour {client},\n\n"
        "Nous vous contactons au sujet du dossier {case_id}. Sauf erreur de notre part, "
        "le montant restant dû est de {amount_due_label}.\n\n"
        "{missed_promise_clause}Le dossier présente un retard de {days_late} jours.\n\n"
        "{schedule_sentence}\n\n"
        "Cordialement,\n"
        "Crédit Aurore"
    ),
)

RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_schedule_card_message_v1",
    template_version="1.0.0",
    template_label="Phrase prudente d'échéancier",
    template_tone="prudent et factuel",
    allowed_use_cases=("propose_schedule",),
    template_body=(
        "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de "
        "validation et d'accord sur les modalités."
    ),
)

RECOUVREMENT_MESSAGE_TEMPLATES: Final = {
    template.template_id: template
    for template in (
        RECOUVREMENT_REMINDER_SHORT_V1,
        RECOUVREMENT_REMINDER_EMPATHIC_V1,
        RECOUVREMENT_SCHEDULE_MESSAGE_V1,
        RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1,
    )
}


def render_schedule_sentence(requested_months: object, monthly_amount_label: object) -> str:
    """Render the bounded schedule sentence embedded in schedule-aware templates."""
    if isinstance(requested_months, int) and isinstance(monthly_amount_label, str):
        return (
            "Une solution d'échelonnement peut être étudiée avec vous, par exemple sur "
            f"{requested_months} mois avec une mensualité indicative de {monthly_amount_label}, "
            "sous réserve de validation interne et d'accord sur les modalités."
        )
    return (
        "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de "
        "validation interne et d'accord sur les modalités."
    )

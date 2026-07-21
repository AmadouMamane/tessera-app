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
_ENGLISH_MONTHS: Final = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_GERMAN_MONTHS: Final = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)

RecouvrementLanguage = Literal["fr", "en", "de"]
TemplateKind = Literal["short", "empathic", "schedule", "schedule_card"]

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


def format_promise_date(promise_date: date, language: RecouvrementLanguage = "fr") -> str:
    """Format a payment-promise date deterministically without host locales."""
    if language == "en":
        return f"{_ENGLISH_MONTHS[promise_date.month - 1]} {promise_date.day}"
    if language == "de":
        return f"{promise_date.day}. {_GERMAN_MONTHS[promise_date.month - 1]}"
    day = "1er" if promise_date.day == 1 else str(promise_date.day)
    return f"{day} {_FRENCH_MONTHS[promise_date.month - 1]}"


def render_missed_promise_clause(
    missed_promise_date: date | None,
    language: RecouvrementLanguage = "fr",
) -> str:
    """Render the broken-promise clause, or nothing when the file records no promise.

    A dunning letter is a regulated artifact: it may only assert a broken payment
    promise when the case file actually carries one. When ``missed_promise_date``
    is ``None`` the clause is omitted entirely rather than defaulted.

    Args:
        missed_promise_date: Date of the broken promise as recorded on the case,
            or ``None`` when the file records none.
        language: Approved output locale for the clause.

    Returns:
        The clause, ending with a separating space, or an empty string.
    """
    if missed_promise_date is None:
        return ""
    promise_day = format_promise_date(missed_promise_date, language)
    if language == "en":
        return f"Your payment commitment dated {promise_day} could not be met. "
    if language == "de":
        return f"Ihre Zahlungszusage vom {promise_day} konnte nicht eingehalten werden. "
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

RECOUVREMENT_REMINDER_SHORT_EN_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_reminder_short_en_v1",
    template_version="1.0.0",
    template_label="friendly reminder",
    template_tone="courteous and factual",
    allowed_use_cases=("draft_reminder",),
    template_body=(
        "Dear {client},\n\n"
        "We are contacting you regarding case {case_id}. Unless our records are incorrect, "
        "the outstanding amount is {amount_due_label}.\n\n"
        "{missed_promise_clause}The case is {days_late} days overdue.\n\n"
        "Please contact us so that we can discuss a solution suited to your situation.\n\n"
        "Kind regards,\nCrédit Aurore"
    ),
)

RECOUVREMENT_REMINDER_EMPATHIC_EN_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_reminder_empathic_en_v1",
    template_version="1.0.0",
    template_label="more empathetic tone",
    template_tone="empathetic",
    allowed_use_cases=("draft_reminder", "rewrite_tone"),
    template_body=(
        "Dear {client},\n\n"
        "We understand that your situation may require a tailored discussion. We would like "
        "to review case {case_id} with you; the outstanding amount is {amount_due_label}.\n\n"
        "{missed_promise_clause}The case is {days_late} days overdue.\n\n"
        "Please contact us so that we can discuss a solution suited to your situation.\n\n"
        "Kind regards,\nCrédit Aurore"
    ),
)

RECOUVREMENT_SCHEDULE_MESSAGE_EN_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_schedule_message_en_v1",
    template_version="1.0.0",
    template_label="customer message with instalment option",
    template_tone="careful and factual",
    allowed_use_cases=("draft_reminder", "prepare_client_message", "propose_schedule"),
    template_body=(
        "Dear {client},\n\n"
        "We are contacting you regarding case {case_id}. Unless our records are incorrect, "
        "the outstanding amount is {amount_due_label}.\n\n"
        "{missed_promise_clause}The case is {days_late} days overdue.\n\n"
        "{schedule_sentence}\n\nKind regards,\nCrédit Aurore"
    ),
)

RECOUVREMENT_SCHEDULE_CARD_MESSAGE_EN_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_schedule_card_message_en_v1",
    template_version="1.0.0",
    template_label="Careful payment-plan sentence",
    template_tone="careful and factual",
    allowed_use_cases=("propose_schedule",),
    template_body=(
        "An instalment arrangement may be considered with you, subject to validation and "
        "agreement on its terms."
    ),
)

RECOUVREMENT_REMINDER_SHORT_DE_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_reminder_short_de_v1",
    template_version="1.0.0",
    template_label="freundliche Mahnung",
    template_tone="freundlich und sachlich",
    allowed_use_cases=("draft_reminder",),
    template_body=(
        "Guten Tag {client},\n\n"
        "wir kontaktieren Sie bezüglich des Vorgangs {case_id}. Sofern unsere Unterlagen "
        "korrekt sind, beträgt der offene Betrag {amount_due_label}.\n\n"
        "{missed_promise_clause}Der Vorgang ist seit {days_late} Tagen überfällig.\n\n"
        "Bitte setzen Sie sich mit uns in Verbindung, damit wir eine für Ihre Situation "
        "geeignete Lösung besprechen können.\n\nMit freundlichen Grüßen,\nCrédit Aurore"
    ),
)

RECOUVREMENT_REMINDER_EMPATHIC_DE_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_reminder_empathic_de_v1",
    template_version="1.0.0",
    template_label="einfühlsamer Ton",
    template_tone="einfühlsam",
    allowed_use_cases=("draft_reminder", "rewrite_tone"),
    template_body=(
        "Guten Tag {client},\n\n"
        "wir verstehen, dass Ihre Situation ein individuelles Gespräch erfordern kann. Wir "
        "möchten den Vorgang {case_id} mit Ihnen besprechen; der offene Betrag beläuft sich "
        "auf {amount_due_label}.\n\n"
        "{missed_promise_clause}Der Vorgang ist seit {days_late} Tagen überfällig.\n\n"
        "Bitte setzen Sie sich mit uns in Verbindung, damit wir eine für Ihre Situation "
        "geeignete Lösung besprechen können.\n\nMit freundlichen Grüßen,\nCrédit Aurore"
    ),
)

RECOUVREMENT_SCHEDULE_MESSAGE_DE_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_schedule_message_de_v1",
    template_version="1.0.0",
    template_label="Kundennachricht mit Ratenzahlungsoption",
    template_tone="vorsichtig und sachlich",
    allowed_use_cases=("draft_reminder", "prepare_client_message", "propose_schedule"),
    template_body=(
        "Guten Tag {client},\n\n"
        "wir kontaktieren Sie bezüglich des Vorgangs {case_id}. Sofern unsere Unterlagen "
        "korrekt sind, beträgt der offene Betrag {amount_due_label}.\n\n"
        "{missed_promise_clause}Der Vorgang ist seit {days_late} Tagen überfällig.\n\n"
        "{schedule_sentence}\n\nMit freundlichen Grüßen,\nCrédit Aurore"
    ),
)

RECOUVREMENT_SCHEDULE_CARD_MESSAGE_DE_V1: Final = RecouvrementMessageTemplate(
    template_id="recouvrement_schedule_card_message_de_v1",
    template_version="1.0.0",
    template_label="Vorsichtiger Ratenplanhinweis",
    template_tone="vorsichtig und sachlich",
    allowed_use_cases=("propose_schedule",),
    template_body=(
        "Eine Ratenzahlung kann gemeinsam geprüft werden, vorbehaltlich der Freigabe und "
        "einer Vereinbarung über die Bedingungen."
    ),
)

RECOUVREMENT_MESSAGE_TEMPLATES: Final = {
    template.template_id: template
    for template in (
        RECOUVREMENT_REMINDER_SHORT_V1,
        RECOUVREMENT_REMINDER_EMPATHIC_V1,
        RECOUVREMENT_SCHEDULE_MESSAGE_V1,
        RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1,
        RECOUVREMENT_REMINDER_SHORT_EN_V1,
        RECOUVREMENT_REMINDER_EMPATHIC_EN_V1,
        RECOUVREMENT_SCHEDULE_MESSAGE_EN_V1,
        RECOUVREMENT_SCHEDULE_CARD_MESSAGE_EN_V1,
        RECOUVREMENT_REMINDER_SHORT_DE_V1,
        RECOUVREMENT_REMINDER_EMPATHIC_DE_V1,
        RECOUVREMENT_SCHEDULE_MESSAGE_DE_V1,
        RECOUVREMENT_SCHEDULE_CARD_MESSAGE_DE_V1,
    )
}

_TEMPLATES_BY_LANGUAGE: Final = {
    "fr": {
        "short": RECOUVREMENT_REMINDER_SHORT_V1,
        "empathic": RECOUVREMENT_REMINDER_EMPATHIC_V1,
        "schedule": RECOUVREMENT_SCHEDULE_MESSAGE_V1,
        "schedule_card": RECOUVREMENT_SCHEDULE_CARD_MESSAGE_V1,
    },
    "en": {
        "short": RECOUVREMENT_REMINDER_SHORT_EN_V1,
        "empathic": RECOUVREMENT_REMINDER_EMPATHIC_EN_V1,
        "schedule": RECOUVREMENT_SCHEDULE_MESSAGE_EN_V1,
        "schedule_card": RECOUVREMENT_SCHEDULE_CARD_MESSAGE_EN_V1,
    },
    "de": {
        "short": RECOUVREMENT_REMINDER_SHORT_DE_V1,
        "empathic": RECOUVREMENT_REMINDER_EMPATHIC_DE_V1,
        "schedule": RECOUVREMENT_SCHEDULE_MESSAGE_DE_V1,
        "schedule_card": RECOUVREMENT_SCHEDULE_CARD_MESSAGE_DE_V1,
    },
}


def recouvrement_template(
    kind: TemplateKind,
    language: RecouvrementLanguage = "fr",
) -> RecouvrementMessageTemplate:
    """Return the explicitly approved template for a task and locale."""
    return _TEMPLATES_BY_LANGUAGE[language][kind]


def render_schedule_sentence(
    requested_months: object,
    monthly_amount_label: object,
    language: RecouvrementLanguage = "fr",
) -> str:
    """Render the bounded schedule sentence embedded in schedule-aware templates."""
    if isinstance(requested_months, int) and isinstance(monthly_amount_label, str):
        if language == "en":
            return (
                f"An instalment arrangement could be considered over {requested_months} months, "
                f"with an indicative monthly payment of {monthly_amount_label}, subject to "
                "internal validation and agreement on the terms."
            )
        if language == "de":
            return (
                f"Eine Ratenzahlung über {requested_months} Monate mit einer unverbindlichen "
                f"Monatsrate von {monthly_amount_label} kann geprüft werden, vorbehaltlich der "
                "internen Freigabe und einer Vereinbarung über die Bedingungen."
            )
        return (
            "Une solution d'échelonnement peut être étudiée avec vous, par exemple sur "
            f"{requested_months} mois avec une mensualité indicative de {monthly_amount_label}, "
            "sous réserve de validation interne et d'accord sur les modalités."
        )
    if language == "en":
        return (
            "An instalment arrangement may be considered with you, subject to internal "
            "validation and agreement on its terms."
        )
    if language == "de":
        return (
            "Eine Ratenzahlung kann gemeinsam geprüft werden, vorbehaltlich der internen "
            "Freigabe und einer Vereinbarung über die Bedingungen."
        )
    return (
        "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de "
        "validation interne et d'accord sur les modalités."
    )

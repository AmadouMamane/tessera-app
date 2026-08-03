"""Account lookup worker — guarded entry into customer account systems.

The worker wraps the :mod:`tessera.agent.tools.account_balance` tool with
the firewall adapter, records the resulting :class:`ToolCallRecord` and
:class:`GuardDecisionRecord` entries on the state, and emits a brief draft
sentence that the reporter can render in the right language.

Customer identity is sourced from state metadata (``customer_id`` in
``conversation_id``-keyed context). For the public demo the value is the
fictional ``"demo-customer-001"``; production resolution lives in
:mod:`tessera.api.middleware`.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal

from tessera.agent.state import AgentState, ToolCallRecord
from tessera.agent.tools import account_balance, card_block, transaction_search
from tessera.guard.adapter import guarded_invoke
from tessera.guard.audit import confirmed_tools
from tessera.settings import LanguageCode

_THIRD_PARTY_RE = re.compile(
    r"\b(collègue|voisin|ami|mari|femme|conjoint|époux|épouse|membre"
    r"|Kollege|Nachbar|Freund|Ehemann|Ehefrau|Ehepartner"
    r"|colleague|neighbor|neighbour|husband|wife|partner|friend"
    r"|numéro\s+\d{5,}|Nummer\s+\d{5,}|number\s+\d{5,})\b",
    re.IGNORECASE,
)

_THIRD_PARTY_REFUSAL: dict[LanguageCode, str] = {
    LanguageCode.FR: (
        "Je ne peux accéder qu'aux informations de votre propre compte. "
        "Je ne suis pas autorisé à consulter le compte d'un tiers."
    ),
    LanguageCode.DE: (
        "Ich kann nur auf Informationen Ihres eigenen Kontos zugreifen. "
        "Ich bin nicht berechtigt, das Konto einer anderen Person einzusehen."
    ),
    LanguageCode.EN: (
        "I can only access information for your own account. "
        "I am not authorised to view a third party's account."
    ),
}

NODE_NAME = "account_lookup"

#: The window this worker asks for. Read by ``tests/unit/test_demo_ledger_does_not_expire.py``,
#: which proves the demo ledger sits inside it on every calendar day rather than on one.
_LOOKBACK_DAYS: Final[int] = 90

_DRAFT_TEMPLATES: dict[LanguageCode, str] = {
    LanguageCode.FR: "Le solde de votre compte {iban_masked} est de {amount} {currency}.",
    LanguageCode.DE: "Der Saldo Ihres Kontos {iban_masked} beträgt {amount} {currency}.",
    LanguageCode.EN: "Your account {iban_masked} balance is {amount} {currency}.",
}

_CONFIRM_CARD: dict[LanguageCode, str] = {
    LanguageCode.FR: (
        "Le blocage de la carte se terminant par {last_four} est irréversible. "
        "Confirmez explicitement cette action pour continuer."
    ),
    LanguageCode.DE: (
        "Die Sperrung der Karte mit der Endnummer {last_four} ist unumkehrbar. "
        "Bestätigen Sie diese Aktion ausdrücklich, um fortzufahren."
    ),
    LanguageCode.EN: (
        "Blocking the card ending in {last_four} is irreversible. "
        "Explicitly confirm this action to continue."
    ),
}

_CARD_BLOCKED: dict[LanguageCode, str] = {
    LanguageCode.FR: (
        "La carte se terminant par {last_four} est bloquée. "
        "Votre référence de suivi est {reference}."
    ),
    LanguageCode.DE: (
        "Die Karte mit der Endnummer {last_four} wurde gesperrt. "
        "Ihre Vorgangsnummer lautet {reference}."
    ),
    LanguageCode.EN: (
        "The card ending in {last_four} has been blocked. "
        "Your tracking reference is {reference}."
    ),
}

_TRANSACTIONS_NONE: dict[LanguageCode, str] = {
    LanguageCode.FR: f"Aucune opération n'a été trouvée sur les {_LOOKBACK_DAYS} derniers jours.",
    LanguageCode.DE: f"In den letzten {_LOOKBACK_DAYS} Tagen wurden keine Buchungen gefunden.",
    LanguageCode.EN: f"No transactions were found in the last {_LOOKBACK_DAYS} days.",
}

_TRANSACTIONS_HEADER: dict[LanguageCode, str] = {
    LanguageCode.FR: "Voici vos opérations récentes :",
    LanguageCode.DE: "Hier sind Ihre letzten Buchungen:",
    LanguageCode.EN: "Here are your recent transactions:",
}


def _card_reason(text: str) -> Literal["lost", "stolen", "fraud_suspected", "customer_request"]:
    lowered = text.casefold()
    if any(word in lowered for word in ("volé", "volee", "volée", "gestohlen", "stolen")):
        return "stolen"
    if any(word in lowered for word in ("perdu", "perdue", "verloren", "lost")):
        return "lost"
    if any(word in lowered for word in ("fraude", "fraud", "betrug")):
        return "fraud_suspected"
    return "customer_request"


_FOUR_DIGITS_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")

#: A group of four digits introduced by a card cue is the card, whatever follows it.
_CARD_CUE_RE = re.compile(
    r"(?:finissant\s+par|se\s+termin\w+\s+par|terminant\s+par|carte"
    r"|endend\s+auf|endet\s+auf|Endnummer|Karte"
    r"|ending\s+(?:in|with)|last\s+four|card)"
    r"\D{0,24}?(?<!\d)(\d{4})(?!\d)",
    re.IGNORECASE,
)

#: 19xx / 20xx read as a year unless a cue says otherwise — see ``_last_four``.
_YEAR_LIKE_RE = re.compile(r"(?:19|20)\d{2}")

#: The authenticated demo customer owns one seeded card. A production connector will
#: resolve the selected card from the authenticated account.
_SEEDED_CARD = "4242"


def _last_four(text: str) -> str:
    """Return the four digits identifying the card the customer is talking about.

    This used to be ``matches[-1]`` — the LAST group of four in the sentence. "ma carte
    finissant par 1234 volée le 12 juillet 2026" therefore opposed card "2026", and the
    customer's real card stayed live. Order is not evidence: a cue is, so a cue wins, a
    year-looking group is skipped, and only then does position decide.
    """
    cued = _CARD_CUE_RE.search(text)
    if cued is not None:
        return cued.group(1)
    candidates: list[str] = _FOUR_DIGITS_RE.findall(text)
    for candidate in candidates:
        if not _YEAR_LIKE_RE.fullmatch(candidate):
            return candidate
    return candidates[0] if candidates else _SEEDED_CARD


def _tool_update(call: ToolCallRecord, decisions: tuple[object, ...]) -> dict[str, object]:
    return {"tool_calls": [call], "guard_decisions": list(decisions)}


def _confirmed_card() -> str | None:
    """Return the card the human actually confirmed, when this turn carries a confirmation.

    The confirmation token binds the card (``guard/policy.yaml``: ``confirmation_binds``), so
    on the confirming turn the card is a fact already established server-side — not something
    to re-read out of a sentence that no longer has to repeat the number.
    """
    return confirmed_tools.get().get("card_block")


async def _block_card(state: AgentState, customer_id: str) -> dict[str, object]:
    last_four = _confirmed_card() or _last_four(state["user_input"])
    reason = _card_reason(state["user_input"])
    arguments: dict[str, object] = {
        "customer_id": customer_id,
        "card_last_four": last_four,
        "reason": reason,
    }
    started = time.perf_counter()
    guarded_result = await guarded_invoke(
        tool_name="card_block",
        invoke=lambda: card_block.block(
            customer_id=customer_id,
            card_last_four=last_four,
            reason=reason,
        ),
        arguments=arguments,
        language=state["language"],
    )
    call = ToolCallRecord(
        tool_name="card_block",
        node=NODE_NAME,
        arguments=arguments,
        result=guarded_result.result,
        succeeded=guarded_result.allowed and guarded_result.error is None,
        error=guarded_result.error,
        started_at=datetime.now(UTC),
        duration_ms=(time.perf_counter() - started) * 1000.0,
    )
    update = _tool_update(call, guarded_result.decisions)
    if call.succeeded and guarded_result.result is not None:
        result = guarded_result.result
        update["draft_response"] = _CARD_BLOCKED[state["language"]].format(
            last_four=result.card_last_four,
            reference=result.ticket_reference,
        )
    elif any(d.policy_rule.endswith("requires_confirmation") for d in guarded_result.decisions):
        update["draft_response"] = _CONFIRM_CARD[state["language"]].format(last_four=last_four)
        update["errors"] = ["account_lookup: policy confirmation required"]
    return update


async def _search_transactions(state: AgentState, customer_id: str) -> dict[str, object]:
    since = date.today() - timedelta(days=_LOOKBACK_DAYS)
    arguments: dict[str, object] = {
        "customer_id": customer_id,
        "since": since.isoformat(),
        "limit": 10,
        "direction": "both",
    }
    started = time.perf_counter()
    guarded_result = await guarded_invoke(
        tool_name="transaction_search",
        invoke=lambda: transaction_search.search(customer_id=customer_id, since=since),
        arguments=arguments,
        language=state["language"],
    )
    call = ToolCallRecord(
        tool_name="transaction_search",
        node=NODE_NAME,
        arguments=arguments,
        result=guarded_result.result,
        succeeded=guarded_result.allowed and guarded_result.error is None,
        error=guarded_result.error,
        started_at=datetime.now(UTC),
        duration_ms=(time.perf_counter() - started) * 1000.0,
    )
    update = _tool_update(call, guarded_result.decisions)
    if call.succeeded and guarded_result.result is not None:
        result = guarded_result.result
        if not result.transactions:
            update["draft_response"] = _TRANSACTIONS_NONE[state["language"]]
        else:
            rows = [
                f"- {txn.posted_at.date().isoformat()} · {txn.label} · {txn.amount} {txn.currency}"
                for txn in result.transactions
            ]
            update["draft_response"] = "\n".join([_TRANSACTIONS_HEADER[state["language"]], *rows])
    return update


async def run(state: AgentState) -> dict[str, object]:
    """Worker entry point."""
    if _THIRD_PARTY_RE.search(state["user_input"]):
        refusal = _THIRD_PARTY_REFUSAL[state["language"]]
        return {"draft_response": refusal, "errors": ["account_lookup: third-party access refused"]}

    customer_id = "demo-customer-001"  # see module docstring
    intents = set(state.get("intents", []))
    if "card_block" in intents:
        return await _block_card(state, customer_id)
    if "transaction_search" in intents:
        return await _search_transactions(state, customer_id)

    started = time.perf_counter()
    guarded_result = await guarded_invoke(
        tool_name="account_balance",
        invoke=lambda: account_balance.fetch(customer_id=customer_id),
        arguments={"customer_id": customer_id},
        language=state["language"],
    )
    duration_ms = (time.perf_counter() - started) * 1000.0

    call = ToolCallRecord(
        tool_name="account_balance",
        node=NODE_NAME,
        arguments={"customer_id": customer_id},
        result=guarded_result.result,
        succeeded=guarded_result.allowed and guarded_result.error is None,
        error=guarded_result.error,
        started_at=datetime.now(UTC),
        duration_ms=duration_ms,
    )

    update: dict[str, object] = {
        "tool_calls": [call],
        "guard_decisions": list(guarded_result.decisions),
    }

    if call.succeeded and guarded_result.result is not None:
        balance = guarded_result.result
        template = _DRAFT_TEMPLATES[state["language"]]
        update["draft_response"] = template.format(
            iban_masked=balance.iban_masked,
            amount=f"{balance.amount:,.2f}",
            currency=balance.currency,
        )
    return update

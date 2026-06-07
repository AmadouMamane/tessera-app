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
from datetime import UTC, datetime

from tessera.agent.state import AgentState, ToolCallRecord
from tessera.agent.tools import account_balance
from tessera.guard.adapter import guarded_invoke
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

_DRAFT_TEMPLATES: dict[LanguageCode, str] = {
    LanguageCode.FR: "Le solde de votre compte {iban_masked} est de {amount} {currency}.",
    LanguageCode.DE: "Der Saldo Ihres Kontos {iban_masked} beträgt {amount} {currency}.",
    LanguageCode.EN: "Your account {iban_masked} balance is {amount} {currency}.",
}


async def run(state: AgentState) -> dict[str, object]:
    """Worker entry point."""
    if _THIRD_PARTY_RE.search(state["user_input"]):
        refusal = _THIRD_PARTY_REFUSAL[state["language"]]
        return {"draft_response": refusal, "errors": ["account_lookup: third-party access refused"]}

    customer_id = "demo-customer-001"  # see module docstring
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
        arguments={"customer_id": customer_id},
        result=guarded_result.result,
        succeeded=guarded_result.allowed and guarded_result.error is None,
        error=guarded_result.error,
        decision_proof_id=(
            guarded_result.decision_proof.decision_id
            if guarded_result.decision_proof is not None
            else None
        ),
        decision_proof_hash=(
            guarded_result.decision_proof.proof_hash
            if guarded_result.decision_proof is not None
            else None
        ),
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

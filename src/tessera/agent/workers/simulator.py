"""Loan-simulator worker — runs a deterministic mortgage simulation.

The simulator is intentionally simple: it parses an amount, a duration, and
an optional rate from the user's input (best-effort, language-aware), calls
the :mod:`tessera.agent.tools.loan_simulate` tool with explicit arguments,
and writes a one-line draft summarising the monthly payment.

When parsing fails (no amount detected, etc.), the worker records the
failure on the state and lets the reviewer decide between asking a
clarifying question (low confidence) and escalating.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime
from typing import Final

from tessera.agent.state import AgentState, ToolCallRecord
from tessera.agent.tools import loan_simulate
from tessera.guard.adapter import guarded_invoke
from tessera.settings import LanguageCode

_MIN_LOAN_AMOUNT: Final = 1000

NODE_NAME = "simulator"

_AMOUNT_RE = re.compile(
    r"(?P<amount>[\d][\d\s.,]*)\s*(?P<currency>€|euros?|EUR)?",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"(?P<years>\d{1,2})\s*(?:ans?|jahre?|year|years|yrs?)",
    re.IGNORECASE,
)

_DRAFT_TEMPLATES: dict[LanguageCode, str] = {
    LanguageCode.FR: (
        "Pour un prêt de {amount} € sur {years} ans au taux indicatif de "
        "{rate}%, la mensualité estimée est de {monthly} €."
    ),
    LanguageCode.DE: (
        "Für ein Darlehen über {amount} € mit einer Laufzeit von {years} "
        "Jahren zum indikativen Zinssatz von {rate}% beträgt die geschätzte "
        "monatliche Rate {monthly} €."
    ),
    LanguageCode.EN: (
        "For a loan of €{amount} over {years} years at an indicative rate "
        "of {rate}%, the estimated monthly payment is €{monthly}."
    ),
}


def _to_float(raw: str) -> float | None:
    normalised = raw.replace(" ", "").replace(",", ".")
    # If multiple dots remain (e.g. "200.000.50"), strip all but the last.
    if normalised.count(".") > 1:
        parts = normalised.split(".")
        normalised = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(normalised)
    except ValueError:
        return None


def _parse_amount(text: str) -> float | None:
    """Return the loan amount stated in ``text``, or ``None`` when there is none.

    This used to read the FIRST number in the sentence and give up when it was too small to
    be an amount. "un prêt sur 20 ans de 250 000 €" therefore parsed ``20``, rejected it as
    noise and returned ``None`` — no simulation, no monthly payment and no escalation, for an
    ordinary French sentence whose only fault was naming the duration first. Word order is not
    evidence: every candidate is read, and one carrying an explicit currency marker wins over
    one that does not.
    """
    fallback: float | None = None
    for match in _AMOUNT_RE.finditer(text):
        value = _to_float(match.group("amount"))
        # Amounts under 1000 are almost certainly noise (years, percentages, months).
        if value is None or value < _MIN_LOAN_AMOUNT:
            continue
        if match.group("currency"):
            return value
        if fallback is None:
            fallback = value
    return fallback


def _parse_years(text: str) -> int | None:
    match = _DURATION_RE.search(text)
    if match is None:
        return None
    try:
        return int(match.group("years"))
    except ValueError:
        return None


async def run(state: AgentState) -> dict[str, object]:
    """Worker entry point."""
    amount = _parse_amount(state["user_input"])
    years = _parse_years(state["user_input"]) or 20  # sensible default

    if amount is None:
        return {"errors": ["simulator: could not parse a loan amount from the request"]}

    rate = 3.5
    arguments: dict[str, object] = {"amount": amount, "years": years, "rate": rate}
    started = time.perf_counter()
    guarded_result = await guarded_invoke(
        tool_name="loan_simulate",
        invoke=lambda: loan_simulate.compute(amount=amount, years=years, rate=rate),
        arguments=arguments,
        language=state["language"],
    )
    duration_ms = (time.perf_counter() - started) * 1000.0

    call = ToolCallRecord(
        tool_name="loan_simulate",
        node=NODE_NAME,
        arguments=arguments,
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
        result = guarded_result.result
        template = _DRAFT_TEMPLATES[state["language"]]
        update["draft_response"] = template.format(
            amount=f"{result.amount:,.0f}",
            years=result.years,
            rate=f"{result.rate:.2f}",
            monthly=f"{result.monthly_payment:,.2f}",
        )
    return update

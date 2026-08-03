"""Two workers read a sentence, and both used to let word order decide.

* ``simulator`` read the FIRST number and gave up when it was too small to be an amount.
  "un prêt sur 20 ans de 250 000 €" parsed ``20``, rejected it as noise and returned
  ``None``: no simulation, no monthly payment, no escalation — for an ordinary French
  sentence whose only fault was naming the duration first.
* ``account_lookup._last_four`` read the LAST group of four digits. "ma carte finissant par
  1234 volée le 12 juillet 2026" therefore opposed card **2026** while the customer's real
  card stayed live, and the confirmation turn — which no longer repeats the number — fell
  back to the seeded ``4242``.

Position in a sentence is not evidence. A cue is.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest

from tessera.agent.state import AgentState, ToolCallRecord, new_state
from tessera.agent.workers import account_lookup, simulator
from tessera.authz import AuthState
from tessera.guard.audit import confirmed_tools, current_auth_state, current_tool_call_counts
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    from collections.abc import Iterator


def _state(text: str, intent: str) -> AgentState:
    state = new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=text,
        language=LanguageCode.FR,
    )
    state["intents"] = [intent]
    state["plan"] = []
    return state


@pytest.fixture
def _as_customer() -> Iterator[None]:
    auth_token = current_auth_state.set(AuthState.CUSTOMER)
    counts_token = current_tool_call_counts.set({})
    try:
        yield
    finally:
        current_tool_call_counts.reset(counts_token)
        current_auth_state.reset(auth_token)


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("un prêt sur 20 ans de 250 000 €", 250_000.0),
        ("Je voudrais un prêt de 250 000 € sur 20 ans", 250_000.0),
        ("sur 25 ans, emprunter 180000 euros", 180_000.0),
        ("Auf 20 Jahre ein Darlehen über 250 000 EUR", 250_000.0),
        ("over 20 years, a loan of 250000 EUR at 3,5 %", 250_000.0),
    ],
)
def test_the_amount_is_found_wherever_it_sits_in_the_sentence(
    sentence: str,
    expected: float,
) -> None:
    assert simulator._parse_amount(sentence) == expected


def test_a_sentence_with_no_amount_still_parses_to_nothing() -> None:
    """Proves the parser can still refuse — it did not just start accepting numbers."""
    assert simulator._parse_amount("sur 20 ans, quel taux proposez-vous ?") is None
    assert simulator._parse_amount("aucun chiffre ici") is None


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("ma carte finissant par 1234 volée le 12 juillet 2026", "1234"),
        ("carte 1234 perdue hier", "1234"),
        ("Bloquez ma carte 4242", "4242"),
        ("Meine Karte mit der Endnummer 1234 wurde am 12.07.2026 gestohlen", "1234"),
        ("my card ending in 1234 was stolen on 12 July 2026", "1234"),
        # No cue at all: a year-looking group is still not a card number.
        ("volée le 12 juillet 2026, le numéro est 1234", "1234"),
    ],
)
def test_the_card_is_the_one_the_customer_named(sentence: str, expected: str) -> None:
    assert account_lookup._last_four(sentence) == expected


def test_with_nothing_to_go_on_the_seeded_card_is_used() -> None:
    assert account_lookup._last_four("Bloquez ma carte s'il vous plaît") == "4242"


@pytest.mark.asyncio
@pytest.mark.usefixtures("_as_customer")
async def test_the_confirmed_card_beats_anything_re_read_from_the_text() -> None:
    """On the confirming turn the card is a server-side fact, not a re-parse.

    The confirmation token binds ``card_last_four`` (``guard/policy.yaml``). A customer who
    says "je confirme" without repeating the number used to fall back to the seeded 4242 —
    which, now that the binding is enforced, would be refused rather than acted on. Either
    way the customer could not block their card.
    """
    confirm_token = confirmed_tools.set({"card_block": "1234"})
    try:
        update = await account_lookup.run(_state("Oui, je confirme.", "card_block"))
    finally:
        confirmed_tools.reset(confirm_token)

    call = cast("list[ToolCallRecord]", update["tool_calls"])[0]
    assert call.arguments["card_last_four"] == "1234"
    assert call.succeeded is True
    assert "1234" in cast("str", update["draft_response"])

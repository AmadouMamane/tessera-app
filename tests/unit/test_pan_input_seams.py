"""Unit tests for the input-side PAN seams (docs/design/pii-input-redaction.md).

Seam 1 — ``reporter._build_chat_messages`` sweeps every message part (current
user content, window verbatim, and with richer backends the summary / entity /
long-term blocks) through ``mask_pan`` before anything reaches the model or the
Debug capture; the sandbox ``pii`` override keeps the playground raw.
Seam 3 — ``entities.mask_ledger_pans`` stores a Luhn-valid PAN captured by the
extractors in its masked form while IBANs and genuine references pass through.

The persistence backstops (transcript / summary / long-term) hit Postgres and
are covered by the integration suite and the live e2e.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pytest

from tessera.agent import reporter
from tessera.agent.state import AgentState, ConversationMessage, new_state
from tessera.memory import get_memory_backend
from tessera.memory.entities import extract_entities, mask_ledger_pans
from tessera.memory.protocol import EntityLedger
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _window_backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Force the hermetic Tier-0 window backend for these tests.

    The seams under test live in the reporter, not the memory tiers; the dev
    ``.env.local`` selects the persistent backend, which would reach Ollama and
    Postgres from a unit test (and leak unclosed sockets into the suite).
    """
    monkeypatch.setenv("TESSERA_MEMORY__BACKEND", "window")
    get_settings.cache_clear()
    get_memory_backend.cache_clear()
    yield
    get_settings.cache_clear()
    get_memory_backend.cache_clear()


_PAN = "4242 4242 4242 4242"
_MASKED = "XXXX XXXX XXXX 4242"
_IBAN = "FR76 3000 6000 0112 3456 7890 189"


def _chat_state(
    user_input: str,
    prior: list[ConversationMessage] | None = None,
    **kwargs: object,
) -> AgentState:
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=user_input,
        language=LanguageCode.FR,
        language_confidence=1.0,
        prior_messages=prior,
        **kwargs,  # type: ignore[arg-type]
    )


async def test_build_chat_messages_masks_every_part() -> None:
    prior = [
        ConversationMessage(role="user", content=f"ma carte {_PAN} est refusée"),
        ConversationMessage(role="assistant", content="Je vérifie cela."),
        ConversationMessage(role="user", content=f"mon IBAN est {_IBAN}"),
        ConversationMessage(role="assistant", content="Merci."),
    ]
    current = f"bloquez la carte {_PAN} s'il vous plaît"
    state = _chat_state(current, prior)
    prompts = reporter.load_prompts(LanguageCode.FR)

    msgs = await reporter._build_chat_messages(state, "Tu es un assistant.", current, prompts)

    joined = "\n".join(m.content for m in msgs)
    assert _PAN not in joined
    assert "4242424242424242" not in joined
    assert joined.count(_MASKED) >= 2  # window verbatim + current user content
    assert _IBAN in joined  # IBANs pass through untouched
    # The Debug capture is the same swept list — sink 5 closes for free.
    debug = cast("list[dict[str, str]]", state["debug_prompt_messages"])
    debug_joined = "\n".join(m["content"] for m in debug)
    assert _PAN not in debug_joined
    assert _MASKED in debug_joined


async def test_build_chat_messages_pii_override_keeps_raw() -> None:
    current = f"bloquez la carte {_PAN}"
    state = _chat_state(current, guard_overrides=["pii"])
    prompts = reporter.load_prompts(LanguageCode.FR)

    msgs = await reporter._build_chat_messages(state, "Tu es un assistant.", current, prompts)

    joined = "\n".join(m.content for m in msgs)
    assert _PAN in joined  # the console playground probes the guard on raw text


def test_mask_ledger_pans_masks_only_luhn_valid_values() -> None:
    text = f"carte n° 4242424242424242, IBAN {_IBAN}, compte n° 00098123, réf. 2024031299887766"
    ledger = extract_entities(text)
    assert "4242424242424242" in ledger.account_refs

    masked = mask_ledger_pans(ledger)
    assert _MASKED in masked.account_refs
    assert "4242424242424242" not in masked.account_refs
    assert _IBAN in masked.account_refs  # IBAN stays, operationally needed
    assert "00098123" in masked.account_refs  # short account number stays
    assert masked.ticket_refs == ledger.ticket_refs  # Luhn-invalid ref untouched


def test_mask_ledger_pans_is_identity_when_clean() -> None:
    ledger = EntityLedger(amounts=("1 250 €",), account_refs=(_IBAN, "00098123"))
    assert mask_ledger_pans(ledger) is ledger

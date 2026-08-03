"""Five places that degraded without saying so, and one that said the opposite of what it did.

Each of these was correct-looking code whose failure mode was silence:

* an IBAN written the way every French bank statement writes it was chopped up by the card
  masker and came out with the account number half unmasked, inside a string the audit trail
  recorded as PII-screened;
* ``strip_format_directives`` cut "answer in 30 days" out of a sentence about a GDPR deadline,
  because any word at all counted as a length unit;
* ``guard.fail_closed`` returned ``allowed=True`` for a tool that had just raised;
* a mistyped ``TESSERA_<section>__<name>`` override was dropped without a word;
* ``provider="vault"`` with a missing URL silently became "read the environment" — the exact
  posture Vault had been configured to replace;
* and the summary buffer threw away the previous summary on every turn, so the start of a long
  conversation left memory permanently while the dashboard went on showing a summary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tessera.agent.state import ConversationMessage
from tessera.guard.adapter import guarded_invoke
from tessera.guard.audit import current_auth_state
from tessera.memory.governance import _mask_secrets
from tessera.memory.window import strip_format_directives
from tessera.settings import (
    LanguageCode,
    Settings as _Settings,
    get_settings,
    unbound_env_overrides,
)

if TYPE_CHECKING:
    from uuid import UUID

# ── PII masking ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "Mon IBAN est FR76 3000 4000 0300 0012 3456 789 pour le virement.",
        "IBAN: FR7630004000030000123456789",
        "Konto DE89 3704 0044 0532 0130 00 bitte.",
        "Please use GB29NWBK60161331926819.",
    ],
)
def test_a_grouped_iban_is_masked_whole(text: str) -> None:
    masked, did_mask = _mask_secrets(text)
    assert did_mask is True
    assert "[IBAN " in masked
    # The failure this pins: the card masker used to eat the middle of the account number and
    # leave both ends in the clear, under a "[card ••••]" label.
    assert "[card" not in masked
    for group in text.split():
        if group.isdigit() and len(group) >= 4:
            assert group not in masked


def test_a_real_card_number_is_still_masked_as_a_card() -> None:
    """Running the IBAN pass first must not have stopped the card pass working."""
    masked, did_mask = _mask_secrets("Ma carte 4242 4242 4242 4242 a été débitée.")
    assert did_mask is True
    assert "[card ••••4242]" in masked


def test_text_without_secrets_is_untouched() -> None:
    masked, did_mask = _mask_secrets("Bonjour, je voudrais un rendez-vous.")
    assert did_mask is False
    assert masked == "Bonjour, je voudrais un rendez-vous."


# ── format directives ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "You must answer in 30 days as required by GDPR Art. 12",
        "Le responsable doit répondre en 30 jours ouvrés selon le RGPD",
        "Die Antwort muss in 30 Tagen erfolgen",
    ],
)
def test_a_regulatory_deadline_is_not_a_format_directive(text: str) -> None:
    assert strip_format_directives(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Explique le prélèvement, réponds en 2 lignes", "Explique le prélèvement"),
        ("Summarise my balance, answer in 3 words", "Summarise my balance"),
        ("Erkläre die Gebühr, antworte in 2 Zeilen", "Erkläre die Gebühr"),
        ("Explique, réponse courte", "Explique"),
    ],
)
def test_a_real_format_directive_is_still_stripped(text: str, expected: str) -> None:
    """Proves the narrowing did not simply disable the stripping."""
    assert strip_format_directives(text) == expected


# ── fail_closed ──────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_tool_that_raises_under_fail_closed_is_not_reported_as_allowed() -> None:
    assert get_settings().guard.fail_closed is True, "this test is about the closed posture"

    def _boom() -> object:
        raise RuntimeError("connector down")

    token = current_auth_state.set(current_auth_state.get())
    try:
        result = await guarded_invoke(
            tool_name="loan_simulate",
            invoke=_boom,
            arguments={"amount": 200000, "years": 20, "rate": 3.5},
            language=LanguageCode.FR,
        )
    finally:
        current_auth_state.reset(token)

    assert result.allowed is False
    assert result.result is None
    assert result.error is not None and "connector down" in result.error


# ── settings overrides ───────────────────────────────────────────────────────────────────


def test_a_mistyped_section_override_is_named() -> None:
    env = {
        "TESSERA_GUARD__FAILCLOSED": "false",  # the typo: no underscore
        "TESSERA_MEMORY__BAKCEND": "window",  # the transposition
    }
    assert unbound_env_overrides(env) == (
        "TESSERA_GUARD__FAILCLOSED",
        "TESSERA_MEMORY__BAKCEND",
    )


def test_every_real_override_binds() -> None:
    """Proves the detector is not simply flagging everything."""
    env = {
        "TESSERA_GUARD__FAIL_CLOSED": "false",
        "TESSERA_GUARD__AUDIT_SINK": "file",
        "TESSERA_MEMORY__BACKEND": "window",
        "TESSERA_API__WORKERS": "4",
        "TESSERA_POSTGRES__DSN": "postgresql://x/y",
    }
    assert unbound_env_overrides(env) == ()


def test_names_outside_a_settings_section_are_left_alone() -> None:
    """Compose, the Makefile and the scripts own plenty of TESSERA_* names. Not our business."""
    env = {
        "TESSERA_SESSION_ID": "abc",
        "TESSERA_BUILD_SHA": "deadbeef",
        "TESSERA_OBS_GRAFANA_PASSWORD": "x",
        "TESSERA_NOT_A_SECTION__ANYTHING": "x",
    }
    assert unbound_env_overrides(env) == ()


def test_the_detector_covers_every_declared_section() -> None:
    """Reads the sections off the model, so a new sub-settings model is covered by birth."""
    from pydantic_settings import BaseSettings

    declared = {
        name
        for name, field in _Settings.model_fields.items()
        if isinstance(field.annotation, type) and issubclass(field.annotation, BaseSettings)
    }
    assert declared, "no nested settings sections found — the detector would police nothing"
    for section in declared:
        planted = f"TESSERA_{section.upper()}__DEFINITELY_NOT_A_FIELD"
        assert unbound_env_overrides({planted: "x"}) == (planted,)


# ── secret provider fall-back ────────────────────────────────────────────────────────────


def test_a_misconfigured_vault_provider_says_it_fell_back(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from tessera import secrets as secrets_mod

    monkeypatch.setattr(secrets_mod, "_WARNED", set())
    monkeypatch.setenv("TESSERA_SECRETS__PROVIDER", "vault")
    monkeypatch.delenv("TESSERA_SECRETS__VAULT_URL", raising=False)
    get_settings.cache_clear()
    secrets_mod.get_secret_provider.cache_clear()
    try:
        provider = secrets_mod.get_secret_provider()
    finally:
        get_settings.cache_clear()
        secrets_mod.get_secret_provider.cache_clear()

    assert isinstance(provider, secrets_mod.EnvSecretProvider)
    assert "falling back to env" in capsys.readouterr().err


# ── summary folding ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_previous_summary_is_folded_into_the_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the fold, the oldest turns of a long conversation leave memory for good.

    Each turn re-summarised the raw transcript from scratch and then truncated it to the
    budget — from the END. So once a conversation outgrew the budget, its beginning was cut,
    nothing carried it forward, and the dashboard went on reporting that a summary existed.
    """
    from tessera.memory import summary as summary_mod
    from tessera.memory.protocol import EntityLedger, MemoryScope, TurnRecord

    seen: dict[str, object] = {}

    async def _fake_load(_conversation_id: UUID) -> tuple[str | None, EntityLedger]:
        return "the customer disputed a 42 € card fee in March", EntityLedger()

    async def _fake_save(_cid: UUID, text: str | None, _entities: EntityLedger) -> None:
        seen["saved"] = text

    monkeypatch.setattr(summary_mod, "load_summary", _fake_load)
    monkeypatch.setattr(summary_mod, "save_summary", _fake_save)

    backend = summary_mod.SummaryBackend(history_window=1)
    monkeypatch.setattr(
        backend,
        "_summarise",
        lambda text, _language, *, previous=None: _record(seen, text, previous),
    )

    scope = MemoryScope(
        conversation_id=uuid4(),
        subject_id="subject-1",
        language=LanguageCode.FR,
    )
    turn = TurnRecord(
        user_input="et le mois suivant ?",
        final_response="…",
        messages=[
            ConversationMessage(role="user", content="j'ai vu des frais de 42 €"),
            ConversationMessage(role="assistant", content="je regarde"),
            ConversationMessage(role="user", content="et le mois suivant ?"),
        ],
        language=LanguageCode.FR,
    )
    await backend._form(scope, turn)

    assert seen["previous"] == "the customer disputed a 42 € card fee in March"
    assert seen["saved"] == "folded summary"


async def _record(seen: dict[str, object], text: str, previous: str | None) -> str:
    seen["older_text"] = text
    seen["previous"] = previous
    return "folded summary"


def test_the_token_budget_is_converted_to_characters() -> None:
    """`memory.token_budget` is declared — and shown to the operator — in TOKENS.

    It was applied to ``len()``, so the summariser received roughly a quarter of the budget
    the cockpit said it had.
    """
    from tessera.memory.summary import _CHARS_PER_TOKEN

    assert _CHARS_PER_TOKEN > 1

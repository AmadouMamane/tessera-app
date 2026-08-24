"""ADR 0030 — the closed registry of operable knobs: validation, precedence, fail-open.

The write path is validation-FIRST: an unknown knob, an uncatalogued model or a blank
reason raises **before any store I/O** — which is also what lets the refusal tests run
without Postgres. A refusal that needed the DB to happen would error here as a
connection failure instead of a ``KnobError``, so the tests pin the ordering too.
"""

from __future__ import annotations

import pytest

from tessera.agent.registry import list_agents
from tessera.api.config_overrides import (
    BUDGET_OVERRUN_KEY,
    CHAT_MODEL_KEY,
    DAILY_BUDGET_KEY,
    KnobError,
    _precedence_keys,
    agent_of_key,
    allowed_chat_models,
    base_chat_model,
    knob_keys,
    resolve_chat_model_override,
    set_override,
)
from tessera.settings import get_settings


def test_the_registry_is_the_org_knob_plus_one_per_fleet_agent() -> None:
    """The key space is derived from the real agent registry, never free-typed.

    ADR 0034 grew the closed registry by the two org-wide budget knobs; it
    stays closed, just larger — this freeze is the witness.
    """
    keys = knob_keys()
    assert keys[0] == CHAT_MODEL_KEY
    assert keys[1:-6] == [f"llm.chat_model.agent.{a.id}" for a in list_agents()]
    # Frozen tail grown three times, all deliberate: ADR 0034 (the two budget knobs),
    # ADR 0053 (the three understanding knobs, 2026-08-23), then the understanding
    # MODEL knob (2026-08-24, same catalogue value space as the chat-model family).
    assert keys[-6:] == [
        DAILY_BUDGET_KEY,
        BUDGET_OVERRUN_KEY,
        "recouvrement.understanding.mode",
        "recouvrement.understanding.confidence_threshold",
        "recouvrement.understanding.timeout_s",
        "recouvrement.understanding.model",
    ]


def test_agent_of_key_names_the_agent_and_only_the_agent() -> None:
    assert agent_of_key(CHAT_MODEL_KEY) is None
    agent = list_agents()[0].id
    assert agent_of_key(f"llm.chat_model.agent.{agent}") == agent


def test_allowed_models_come_from_the_real_catalogue() -> None:
    """The value space is the catalogue the page shows — including the frozen base."""
    allowed = allowed_chat_models()
    assert get_settings().ollama.chat_model in allowed
    assert base_chat_model() in allowed


async def test_an_unknown_knob_is_refused_before_any_store_io() -> None:
    with pytest.raises(KnobError, match="closed"):
        await set_override("llm.rate_limit", "x", author="probe", reason="r")


async def test_an_uncatalogued_model_is_refused_never_stored() -> None:
    with pytest.raises(KnobError, match="catalogue"):
        await set_override(CHAT_MODEL_KEY, "gpt-imaginary-99", author="probe", reason="r")


async def test_a_blank_reason_is_refused() -> None:
    model = sorted(allowed_chat_models())[0]
    with pytest.raises(KnobError, match="reason"):
        await set_override(CHAT_MODEL_KEY, model, author="probe", reason="   ")


async def test_budget_ceiling_values_are_validated_per_family() -> None:
    """ADR 0034 — each knob family owns its value space; refusal is pre-store I/O."""
    with pytest.raises(KnobError, match="decimal"):
        await set_override(DAILY_BUDGET_KEY, "beaucoup", author="probe", reason="r")
    with pytest.raises(KnobError, match="positive"):
        await set_override(DAILY_BUDGET_KEY, "-3", author="probe", reason="r")
    with pytest.raises(KnobError, match="positive"):
        await set_override(DAILY_BUDGET_KEY, "0", author="probe", reason="r")


async def test_overrun_behaviour_is_a_closed_set() -> None:
    with pytest.raises(KnobError, match="refused"):
        await set_override(BUDGET_OVERRUN_KEY, "shrug", author="probe", reason="r")
    # A model id is not a behaviour either — the families do not leak into
    # each other's value space.
    with pytest.raises(KnobError, match="refused"):
        await set_override(BUDGET_OVERRUN_KEY, base_chat_model(), author="probe", reason="r")


def test_precedence_is_agent_then_org() -> None:
    """ADR 0030 §3 — the agent's own knob outranks the org-wide knob; never the reverse."""
    agent = list_agents()[0].id
    assert _precedence_keys(agent) == [f"llm.chat_model.agent.{agent}", CHAT_MODEL_KEY]
    assert _precedence_keys(None) == [CHAT_MODEL_KEY]


async def test_resolution_fails_open_to_base_and_says_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Store down ⇒ ``None`` (the frozen base serves) AND a loud log line.

    Both halves matter: a turn must never be blocked by the override store, and a
    silent ``None`` would be indistinguishable from "I looked and there is no
    override" — the blind-witness lie ADR 0026 forbids.
    """

    def _boom() -> object:
        raise RuntimeError("postgres down")

    monkeypatch.setattr("tessera.api.config_overrides.get_pool", _boom)
    assert await resolve_chat_model_override("recouvrement") is None
    assert "serving base" in capsys.readouterr().err

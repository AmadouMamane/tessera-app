"""A model the org can serve but the price table has never heard of spends nothing.

``estimate_turn_cost`` resolves an unknown model to the on-prem provider at zero marginal
cost. For a local Ollama model that is the honest figure. For a *paid* model whose tariff
nobody wrote down it is a hole with a specific shape: the turn is billed by the vendor,
counted at 0.00 € by Tessera, and therefore invisible to the daily ceiling — ``model_is_paid``
returns False, so ADR 0034's breaker never even looks at it. The org burns a frontier model
all day against a breaker reading zero.

The catalogue of servable chat models and the price table are two lists maintained by hand,
and nothing made them meet. This is where they meet.
"""

from __future__ import annotations

from decimal import Decimal

from tessera.llm.budget import estimate_turn_cost, model_is_paid, priced_models


def test_every_servable_chat_model_is_in_the_price_table() -> None:
    from tessera.api.config_overrides import allowed_chat_models

    servable = allowed_chat_models()
    assert servable, "no servable chat models — this witness would police nothing"
    unpriced = sorted(servable - priced_models())
    assert not unpriced, (
        "these models can be served but carry no entry in the price table, so every turn "
        "they run is counted at 0.00 € and the daily ceiling cannot see them:\n  "
        + "\n  ".join(unpriced)
        + "\nAdd them to `_PRICES` in src/tessera/llm/budget.py — with an explicit zero for "
        "local inference, which is a price, not an absence."
    )


def test_a_priced_local_model_is_zero_and_not_paid() -> None:
    """Zero must stay expressible: on-prem inference is free, and says so on purpose."""
    provider, cost = estimate_turn_cost(
        model="llama3.3:70b", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert provider == "ollama"
    assert cost == Decimal(0)
    assert model_is_paid("llama3.3:70b") is False


def test_a_priced_frontier_model_is_paid() -> None:
    """Proves the predicate can still say yes — otherwise the test above proves nothing."""
    assert model_is_paid("gemini-2.0-flash-001") is True
    assert model_is_paid("gpt-5.5") is True


def test_an_unknown_model_still_falls_back_rather_than_raising() -> None:
    """The fall-back is deliberate; what was missing is anything watching the gap."""
    provider, cost = estimate_turn_cost(model="not-a-model", input_tokens=10, output_tokens=10)
    assert provider == "ollama"
    assert cost == Decimal(0)
    assert "not-a-model" not in priced_models()

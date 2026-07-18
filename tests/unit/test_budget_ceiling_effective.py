"""ADR 0034 — the daily LLM budget ceiling is an operable, governed knob.

The tracker was a meter with no breaker (and its docstring claimed caps nobody
enforced). These witnesses interrogate the new breaker end to end:

* the tracker knows what a day is — counters roll on the Europe/Paris day,
  survive a restart within the day, and reset across days;
* ``model_is_paid`` derives from the real price table;
* the seam gates PAID models only: block seeds the state flag, local_fallback
  swaps to the zero-cost base, an under-ceiling day passes untouched;
* the router short-circuits a blocked turn with the localized YAML message;
* the policy read fails open to "no ceiling", loudly.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest

from tessera.agent import router as agent_router
from tessera.agent.reporter import load_prompts
from tessera.agent.state import new_state
from tessera.api import config_overrides
from tessera.api.config_overrides import BudgetPolicy
from tessera.llm import budget
from tessera.llm.budget import BudgetSnapshot, BudgetTracker, model_is_paid
from tessera.settings import LanguageCode

# --------------------------------------------------------------------------- #
# The tracker — a day is a real accounting window
# --------------------------------------------------------------------------- #


def test_day_counters_roll_on_a_new_day(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(budget, "_today", lambda: "2026-07-18")
    tracker = BudgetTracker(persist_path=tmp_path / "budget.json")
    tracker.record(backend="openai", model="gpt-5.5", input_tokens=1_000_000, output_tokens=0)
    snap = tracker.snapshot()
    assert snap.day == "2026-07-18"
    assert snap.day_cost_eur == Decimal("1.10")
    assert snap.estimated_cost_eur == Decimal("1.10")

    monkeypatch.setattr(budget, "_today", lambda: "2026-07-19")
    rolled = tracker.snapshot()
    assert rolled.day == "2026-07-19"
    assert rolled.day_cost_eur == Decimal("0")  # yesterday is gone, said plainly
    assert rolled.estimated_cost_eur == Decimal("1.10")  # cumulative survives


def test_day_counters_survive_a_restart_within_the_day(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(budget, "_today", lambda: "2026-07-18")
    path = tmp_path / "budget.json"
    first = BudgetTracker(persist_path=path)
    first.record(backend="openai", model="gpt-5.5", input_tokens=1_000_000, output_tokens=0)

    reborn = BudgetTracker(persist_path=path)
    assert reborn.snapshot().day_cost_eur == Decimal("1.10")

    # A restart on a LATER day starts a fresh window from the same file.
    monkeypatch.setattr(budget, "_today", lambda: "2026-07-20")
    later = BudgetTracker(persist_path=path)
    assert later.snapshot().day_cost_eur == Decimal("0")
    assert later.snapshot().estimated_cost_eur == Decimal("1.10")


def test_model_is_paid_reads_the_real_price_table() -> None:
    assert model_is_paid("gpt-5.5") is True
    assert model_is_paid("gemini-2.0-flash-001") is True
    assert model_is_paid("llama3.3:70b") is False  # on-prem: zero marginal cost
    assert model_is_paid("llama3.2:3b") is False  # unpriced -> zero -> never gated


# --------------------------------------------------------------------------- #
# The policy read — fails open to "no ceiling", loudly
# --------------------------------------------------------------------------- #


async def test_resolve_budget_policy_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    async def _boom() -> None:
        msg = "store down"
        raise RuntimeError(msg)

    monkeypatch.setattr(config_overrides, "ensure_overrides_schema", _boom)
    assert await config_overrides.resolve_budget_policy() is None
    assert "budget read failed" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# The seam — the breaker gates PAID models only, and says what it did
# --------------------------------------------------------------------------- #


class _FakeTracker:
    def __init__(self, day_cost: str) -> None:
        self._day_cost = Decimal(day_cost)

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            input_tokens=0,
            output_tokens=0,
            estimated_cost_eur=self._day_cost,
            day="2026-07-18",
            day_cost_eur=self._day_cost,
        )


def _probe_route(
    monkeypatch: pytest.MonkeyPatch,
    *,
    policy: BudgetPolicy | None,
    day_cost: str,
    request_model: str | None,
) -> dict[str, Any]:
    """POST /chat with a stubbed policy + tracker; return the state ainvoke saw."""
    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    async def _policy() -> BudgetPolicy | None:
        return policy

    monkeypatch.setattr(chat_route, "resolve_budget_policy", _policy)
    monkeypatch.setattr(chat_route, "get_budget_tracker", lambda: _FakeTracker(day_cost))

    seen: dict[str, Any] = {}

    class _ProbeGraph:
        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            seen.update(state)
            msg = "probe: the turn stops here"
            raise RuntimeError(msg)

    monkeypatch.setattr(chat_route, "_streaming_graph", lambda: _ProbeGraph())

    async def _no_prior_agent(_conversation_id: object) -> None:
        return None

    monkeypatch.setattr(chat_route, "last_agent_for", _no_prior_agent)
    body: dict[str, Any] = {"message": "un tour de test"}
    if request_model is not None:
        body["model"] = request_model
    response = TestClient(build_app()).post("/chat", json=body)
    assert response.status_code == 200
    assert "turn.error" in response.text  # the probe raised: the graph really ran
    return seen


def test_overrun_block_seeds_the_state_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _probe_route(
        monkeypatch,
        policy=BudgetPolicy(daily_eur=Decimal("1"), overrun="block"),
        day_cost="5",
        request_model="gpt-5.5",
    )
    assert state.get("budget_blocked") is True
    assert state.get("model") == "gpt-5.5"  # the model is recorded; the router blocks


def test_overrun_local_fallback_serves_the_free_base(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _probe_route(
        monkeypatch,
        policy=BudgetPolicy(daily_eur=Decimal("1"), overrun="local_fallback"),
        day_cost="5",
        request_model="gpt-5.5",
    )
    assert "budget_blocked" not in state
    assert state.get("model") == config_overrides.base_chat_model()  # zero-cost base serves


def test_under_the_ceiling_nothing_is_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _probe_route(
        monkeypatch,
        policy=BudgetPolicy(daily_eur=Decimal("100"), overrun="block"),
        day_cost="5",
        request_model="gpt-5.5",
    )
    assert "budget_blocked" not in state
    assert state.get("model") == "gpt-5.5"


def test_a_free_model_is_never_gated(monkeypatch: pytest.MonkeyPatch) -> None:
    """The breaker gates PAID models only — local inference always serves."""
    state = _probe_route(
        monkeypatch,
        policy=BudgetPolicy(daily_eur=Decimal("1"), overrun="block"),
        day_cost="5",
        request_model=None,  # the free on-prem base serves
    )
    assert "budget_blocked" not in state


# --------------------------------------------------------------------------- #
# The router — a blocked turn short-circuits with the localized message
# --------------------------------------------------------------------------- #


def test_router_short_circuits_a_budget_blocked_turn() -> None:
    state = new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input="Quel est le taux du Livret A ?",
        language=LanguageCode.FR,
        language_confidence=1.0,
    )
    state["budget_blocked"] = True
    update = agent_router.run(state)
    expected = load_prompts(LanguageCode.FR)["budget_exceeded"].strip()
    assert update["final_response"] == expected
    assert update["plan"] == []
    assert "budget" in str(update["plan_rationale"])


@pytest.mark.parametrize("language", [LanguageCode.FR, LanguageCode.DE, LanguageCode.EN])
def test_every_bundle_carries_the_budget_message(language: LanguageCode) -> None:
    assert load_prompts(language).get("budget_exceeded", "").strip()

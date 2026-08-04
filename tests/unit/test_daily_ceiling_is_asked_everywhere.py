"""ADR 0034 — every path that spends asks the ceiling, and a refusal reads as a refusal.

The ratchet next door (`test_llm_paths_outside_the_ceiling.py`) is a *static* witness: it
reads the source and asserts that no module names an LLM factory without also naming the
ceiling. That catches a forgotten wire, and nothing else — a module could import
``resolve_spend_model`` and never call it, and the ratchet would go green.

So these are the behavioural witnesses. They ask the functions, not the file:

* the gate itself applies the chat route's rule, including the two ways it fails open;
* the policy is cached and the **spend is not**, because caching the crossing would let a
  probe keep spending for a TTL after the breaker tripped;
* each wired module actually refuses — and refuses in the way its own position demands: the
  probes raise, the two memory paths degrade without breaking the turn already answered;
* the refusal reaches an HTTP caller as 402 with its numbers, never as an empty report.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from tessera.api.config_overrides import BudgetPolicy
from tessera.llm import ceiling

if TYPE_CHECKING:
    from collections.abc import Sequence


_PAID = "gemini-2.0-pro-001"  # priced in the real table, so `model_is_paid` says yes
_FREE = "llama3.2:3b"  # local, zero marginal cost


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    ceiling.invalidate_policy_cache()


def _spend(eur: str) -> Any:
    class _Snapshot:
        day_cost_eur = Decimal(eur)

    class _Tracker:
        def snapshot(self) -> _Snapshot:
            return _Snapshot()

    return _Tracker()


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    policy: BudgetPolicy | None,
    spent: str,
    base: str = _FREE,
) -> None:
    async def _policy() -> BudgetPolicy | None:
        return policy

    monkeypatch.setattr(ceiling, "_policy", _policy)
    monkeypatch.setattr(ceiling, "get_budget_tracker", lambda: _spend(spent))
    monkeypatch.setattr(
        "tessera.api.config_overrides.base_chat_model",
        lambda: base,
    )


class TestTheGateAppliesTheChatRoutesRule:
    async def test_no_stored_ceiling_means_no_ceiling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fails open: the known-good deployment is the one with no breaker."""
        _wire(monkeypatch, policy=None, spent="9999")
        assert await ceiling.resolve_spend_model(caller="probe", model=_PAID) == _PAID

    async def test_a_free_model_is_never_gated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A local inference does not spend euros, so a euro ceiling has nothing to say."""
        _wire(monkeypatch, policy=BudgetPolicy(daily_eur=Decimal("1"), overrun="block"), spent="99")
        assert await ceiling.resolve_spend_model(caller="probe", model=_FREE) == _FREE

    async def test_under_the_ceiling_serves_the_intended_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire(
            monkeypatch,
            policy=BudgetPolicy(daily_eur=Decimal("10"), overrun="block"),
            spent="9.99",
        )
        assert await ceiling.resolve_spend_model(caller="probe", model=_PAID) == _PAID

    async def test_over_the_ceiling_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _wire(
            monkeypatch, policy=BudgetPolicy(daily_eur=Decimal("10"), overrun="block"), spent="10"
        )
        with pytest.raises(ceiling.DailyCeilingReachedError) as caught:
            await ceiling.resolve_spend_model(caller="observability.replay", model=_PAID)
        assert caught.value.caller == "observability.replay"
        assert caught.value.ceiling_eur == Decimal("10")
        assert caught.value.day_spend_eur == Decimal("10")
        assert "10" in str(caught.value)

    async def test_local_fallback_serves_the_free_base(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _wire(
            monkeypatch,
            policy=BudgetPolicy(daily_eur=Decimal("10"), overrun="local_fallback"),
            spent="12",
            base=_FREE,
        )
        assert await ceiling.resolve_spend_model(caller="probe", model=_PAID) == _FREE

    async def test_a_fallback_onto_a_paid_base_is_not_a_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The chat route degrades this to a block; so must the gate, or they disagree."""
        _wire(
            monkeypatch,
            policy=BudgetPolicy(daily_eur=Decimal("10"), overrun="local_fallback"),
            spent="12",
            base=_PAID,
        )
        with pytest.raises(ceiling.DailyCeilingReachedError):
            await ceiling.resolve_spend_model(caller="probe", model=_PAID)


class TestTheCacheCachesThePolicyAndNotTheSpend:
    async def test_the_policy_is_read_once_within_the_ttl(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reads = 0

        async def _resolve() -> BudgetPolicy | None:
            nonlocal reads
            reads += 1
            return BudgetPolicy(daily_eur=Decimal("10"), overrun="block")

        monkeypatch.setattr("tessera.api.config_overrides.resolve_budget_policy", _resolve)
        monkeypatch.setattr(ceiling, "get_budget_tracker", lambda: _spend("0"))
        for _ in range(5):
            await ceiling.resolve_spend_model(caller="probe", model=_PAID)
        assert reads == 1, f"the stored ceiling was read {reads} times for five checks"

    async def test_the_spend_is_re_read_every_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The whole asymmetry: a cached spend would let a probe overrun for a TTL."""
        reads = 0

        def _tracker() -> Any:
            nonlocal reads
            reads += 1
            return _spend("0")

        _wire(monkeypatch, policy=BudgetPolicy(daily_eur=Decimal("10"), overrun="block"), spent="0")
        monkeypatch.setattr(ceiling, "get_budget_tracker", _tracker)
        for _ in range(3):
            await ceiling.resolve_spend_model(caller="probe", model=_PAID)
        assert reads == 3

    async def test_a_no_ceiling_answer_is_cached_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`None` is a real answer — re-reading it per probe call would hit Postgres per turn."""
        reads = 0

        async def _resolve() -> BudgetPolicy | None:
            nonlocal reads
            reads += 1
            return None

        monkeypatch.setattr("tessera.api.config_overrides.resolve_budget_policy", _resolve)
        await ceiling.resolve_spend_model(caller="probe", model=_PAID)
        await ceiling.resolve_spend_model(caller="probe", model=_PAID)
        assert reads == 1

    async def test_invalidating_forces_a_fresh_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        reads = 0

        async def _resolve() -> BudgetPolicy | None:
            nonlocal reads
            reads += 1
            return None

        monkeypatch.setattr("tessera.api.config_overrides.resolve_budget_policy", _resolve)
        await ceiling.resolve_spend_model(caller="probe", model=_PAID)
        ceiling.invalidate_policy_cache()
        await ceiling.resolve_spend_model(caller="probe", model=_PAID)
        assert reads == 2


class TestEachWiredModuleActuallyRefuses:
    """Asked of the functions. The static ratchet cannot tell an import from a call."""

    @pytest.fixture(autouse=True)
    def _over_the_ceiling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _wire(
            monkeypatch,
            policy=BudgetPolicy(daily_eur=Decimal("1"), overrun="block"),
            spent="99",
            base=_PAID,
        )

    async def test_the_ablation_probe_raises_rather_than_returning_an_empty_report(self) -> None:
        from tessera.observability import ablation

        with pytest.raises(ceiling.DailyCeilingReachedError):
            await ablation.measure_ablation(question="q", context="c", model=_PAID, baseline=0.5)

    async def test_the_consistency_probe_raises(self) -> None:
        from tessera.observability import consistency

        with pytest.raises(ceiling.DailyCeilingReachedError):
            await consistency.measure_consistency(question="q", context="c", model=_PAID)

    async def test_the_robustness_probe_raises(self) -> None:
        from tessera.observability import robustness

        with pytest.raises(ceiling.DailyCeilingReachedError):
            await robustness.measure_robustness(question="q", context="c", model=_PAID)

    async def test_the_crosslingual_probe_raises(self) -> None:
        from tessera.observability import crosslingual

        with pytest.raises(ceiling.DailyCeilingReachedError):
            await crosslingual.measure_crosslingual(question="q", context="c", model=_PAID)

    async def test_the_judge_raises(self) -> None:
        from tessera.observability.eval.judge import LLMJudge

        judge = LLMJudge(backend=_NeverCalled(), model=_PAID)
        with pytest.raises(ceiling.DailyCeilingReachedError):
            await judge.score(metric="faithfulness", question="q", answer="a", context="c")

    async def test_the_corpus_translator_raises(self) -> None:
        from tessera.corpus import translator

        with pytest.raises(ceiling.DailyCeilingReachedError):
            await translator.translate_page(text="bonjour", target="de")


class _NeverCalled:
    """A backend that fails the test if the gate let a call through."""

    name = "never-called"

    async def chat(self, messages: Sequence[Any], **kwargs: Any) -> Any:
        msg = "a backend was called after the ceiling refused"
        raise AssertionError(msg)


class TestTheMemoryPathsDegradeWithoutBreakingTheTurn:
    """These run AFTER the turn is answered. Raising here would turn a budget cap into an
    outage — and returning a quiet empty would be indistinguishable from "nothing to record"."""

    @pytest.fixture(autouse=True)
    def _over_the_ceiling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _wire(
            monkeypatch,
            policy=BudgetPolicy(daily_eur=Decimal("1"), overrun="block"),
            spent="99",
            base=_PAID,
        )

    async def test_the_reflector_returns_no_facts_and_says_why(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from tessera.memory.protocol import TurnRecord
        from tessera.memory.reflector import _extract_facts
        from tessera.settings import LanguageCode

        turn = TurnRecord(
            user_input="mon IBAN change",
            final_response="noté",
            messages=[],
            language=LanguageCode.FR,
        )
        assert await _extract_facts(turn) == []
        err = capsys.readouterr().err
        assert "memory.reflector" in err
        assert "ceiling" in err.lower()


class TestTheRefusalReachesTheCallerAsARefusal:
    def test_the_app_answers_402_with_the_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from starlette.testclient import TestClient

        from tessera.api.main import build_app

        app = build_app()

        @app.get("/_ceiling_probe")
        async def _probe() -> dict[str, str]:
            _wire(
                monkeypatch,
                policy=BudgetPolicy(daily_eur=Decimal("7"), overrun="block"),
                spent="8",
                base=_PAID,
            )
            await ceiling.resolve_spend_model(caller="observability.ablation", model=_PAID)
            return {"unreachable": "true"}

        # No `with`: entering the client runs the app LIFESPAN, which opens and then closes
        # the process-wide connection pool — and a closed pool cannot be reopened, so every
        # later test in the process inherits a dead one. The handler under test is registered
        # at build time and needs no startup.
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/_ceiling_probe")
        assert response.status_code == 402, (
            "a refused spend answered "
            f"{response.status_code} — anything in the 2xx range would make a refusal look "
            "like a measurement"
        )
        body = response.json()
        assert body["error"] == "daily_ceiling_reached"
        assert body["caller"] == "observability.ablation"
        assert body["ceiling_eur"] == "7"
        assert body["day_spend_eur"] == "8"

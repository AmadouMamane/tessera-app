"""ADR 0033 — the escalation threshold is an operable, governed knob.

Same witness discipline as ADR 0031/0032: each test interrogates the THING
(ADR 0026), so the threshold can never quietly go back to being frozen:

* the resolver returns the agent's bar, else the org settings value — the same
  read the Configurations page displays; fail-open, loudly;
* the chat ROUTE puts the resolved bar into the graph's initial state
  (captured inside ``ainvoke``);
* the reviewer judges against THE STATE's bar — and keeps the historical
  settings read on states that never crossed the seam (the eval harness stays
  deterministic);
* the save-side coercion clamps to [0, 1] like every slider.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from tessera.agent import reviewer
from tessera.agent.state import AgentState, new_state
from tessera.observability import agent_configurations as configurations
from tessera.settings import LanguageCode, get_settings

# --------------------------------------------------------------------------- #
# The resolver — agent bar, else the org settings value
# --------------------------------------------------------------------------- #


def test_resolver_default_is_the_org_settings_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(configurations, "_load_overrides", lambda *_a: {})
    expected = float(get_settings().guard.escalation_confidence_threshold)
    assert configurations.resolve_escalation_threshold("support-client") == expected


def test_resolver_honours_the_agent_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        configurations, "_load_overrides", lambda *_a: {"escalation_threshold": 0.85}
    )
    assert configurations.resolve_escalation_threshold("recouvrement") == 0.85


def test_resolver_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(*_a: object) -> dict[str, object]:
        msg = "store corrupt"
        raise RuntimeError(msg)

    monkeypatch.setattr(configurations, "_effective", _boom)
    expected = float(get_settings().guard.escalation_confidence_threshold)
    assert configurations.resolve_escalation_threshold() == expected
    assert "resolve_escalation_threshold" in capsys.readouterr().err


def test_save_side_coercion_clamps_to_unit_interval() -> None:
    assert configurations._coerce("escalation_threshold", 1.7) == 1.0
    assert configurations._coerce("escalation_threshold", -0.3) == 0.0
    assert configurations._coerce("escalation_threshold", None) is None
    assert configurations._coerce("escalation_threshold", 0.45) == 0.45


# --------------------------------------------------------------------------- #
# The route seam — the graph's initial state carries the resolved bar
# --------------------------------------------------------------------------- #


def test_chat_route_puts_the_threshold_into_the_graph_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    monkeypatch.setattr(
        configurations, "_load_overrides", lambda *_a: {"escalation_threshold": 0.9}
    )

    class _ProbeGraph:
        def __init__(self) -> None:
            self.threshold: object = None

        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            self.threshold = state.get("escalation_threshold")
            msg = "probe: the turn stops here"
            raise RuntimeError(msg)

    probe = _ProbeGraph()
    monkeypatch.setattr(chat_route, "_streaming_graph", lambda: probe)

    async def _no_prior_agent(_conversation_id: object) -> None:
        return None

    monkeypatch.setattr(chat_route, "last_agent_for", _no_prior_agent)
    client = TestClient(build_app())
    response = client.post("/chat", json={"message": "un tour de test"})
    assert response.status_code == 200
    assert "turn.error" in response.text  # the probe raised: the graph really ran
    assert probe.threshold == 0.9


# --------------------------------------------------------------------------- #
# The reviewer — judges against the state's bar; settings only off-seam
# --------------------------------------------------------------------------- #


def _neutral_state() -> AgentState:
    """No draft, no plan, no guard decision → confidence exactly 0.75.

    grounding 0.5 x 0.5 + coverage 1.0 x 0.3 + guard 1.0 x 0.2 = 0.75 — a fixed
    point the threshold assertions can straddle deterministically.
    """
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input="Bonjour",
        language=LanguageCode.FR,
        language_confidence=1.0,
    )


def test_reviewer_escalates_under_the_state_bar() -> None:
    state = _neutral_state()
    state["escalation_threshold"] = 0.9
    outcome = reviewer.review(state)
    assert outcome.confidence == pytest.approx(0.75)
    assert outcome.needs_escalation is True
    assert outcome.reason is not None
    assert "0.90" in outcome.reason  # the reason names the bar that judged


def test_reviewer_stays_over_the_state_bar() -> None:
    state = _neutral_state()
    state["escalation_threshold"] = 0.5
    outcome = reviewer.review(state)
    assert outcome.needs_escalation is False


def test_reviewer_off_seam_keeps_the_settings_read() -> None:
    """A state that never crossed the seam (eval harness) is judged by settings."""
    outcome = reviewer.review(_neutral_state())
    settings_bar = float(get_settings().guard.escalation_confidence_threshold)
    assert outcome.needs_escalation is (outcome.confidence < settings_bar)
    assert outcome.needs_escalation is False  # 0.75 ≥ 0.6, the frozen default

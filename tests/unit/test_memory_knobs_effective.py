"""ADR 0036 — the memory tier and window are per-agent, effective by construction.

Witnesses, ADR 0026 style:

* the resolver emits only what the agent SET — "Défaut org" is honest absence
  (the settings-selected backend serves), never a copied value; fail-open,
  loudly;
* the chat ROUTE puts the knobs into the graph state (captured inside
  ``ainvoke``);
* ``memory_backend_for`` returns the org singleton when nothing is set, a
  cached per-(tier, window) instance otherwise — same pair, same object;
* the reporter's message assembly resolves its backend FROM THE STATE;
* the save-side coercion clamps the window to [2, 20] whole and maps localized
  tier values back to the canonical French identity.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest

from tessera.agent import reporter
from tessera.agent.state import AgentState, new_state
from tessera.llm.router import ChatMessage, ChatResponse
from tessera.memory import get_memory_backend, memory_backend_for
from tessera.memory.summary import SummaryBackend
from tessera.memory.window import WindowBackend
from tessera.observability import agent_configurations as configurations
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

# --------------------------------------------------------------------------- #
# The resolver
# --------------------------------------------------------------------------- #


def test_resolver_default_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """'Défaut org' + unset window → {}: the org singleton serves, said by absence."""
    monkeypatch.setattr(configurations, "_load_overrides", lambda *_a: {})
    assert configurations.resolve_memory("support-client") == {}


def test_resolver_follows_the_stored_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        configurations,
        "_load_overrides",
        lambda *_a: {"memory_backend": "Résumé (Tier 1)", "memory_window": 4},
    )
    assert configurations.resolve_memory("onboarding") == {"tier": "summary", "window": 4}


def test_resolver_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def _boom(*_a: object) -> dict[str, object]:
        msg = "store corrupt"
        raise RuntimeError(msg)

    monkeypatch.setattr(configurations, "_effective", _boom)
    assert configurations.resolve_memory() == {}
    assert "resolve_memory" in capsys.readouterr().err


def test_window_coercion_clamps_and_tier_values_canonicalize() -> None:
    assert configurations._coerce("memory_window", 50) == 20.0
    assert configurations._coerce("memory_window", 1) == 2.0
    assert configurations._coerce("memory_window", None) is None
    # A localized value posted by the UI maps back to the canonical identity.
    assert configurations._coerce("memory_backend", "Summary (Tier 1)") == "Résumé (Tier 1)"
    assert configurations._coerce("memory_backend", "Org-Standard") == "Défaut org"


# --------------------------------------------------------------------------- #
# The route seam
# --------------------------------------------------------------------------- #


def test_chat_route_puts_the_memory_knobs_into_the_graph_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    monkeypatch.setattr(
        configurations,
        "_load_overrides",
        lambda *_a: {"memory_backend": "Fenêtre (Tier 0)", "memory_window": 3},
    )

    class _ProbeGraph:
        def __init__(self) -> None:
            self.memory: object = None

        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            self.memory = state.get("memory")
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
    assert "turn.error" in response.text
    assert probe.memory == {"tier": "window", "window": 3}


# --------------------------------------------------------------------------- #
# The factory — org singleton by default, cached per pair otherwise
# --------------------------------------------------------------------------- #


@pytest.fixture
def _window_org(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hermetic org default (the dev .env.local could select anything)."""
    monkeypatch.setenv("TESSERA_MEMORY__BACKEND", "window")
    get_settings.cache_clear()
    get_memory_backend.cache_clear()
    yield
    get_settings.cache_clear()
    get_memory_backend.cache_clear()


@pytest.mark.usefixtures("_window_org")
def test_factory_defaults_to_the_org_singleton() -> None:
    assert memory_backend_for(None, None) is get_memory_backend()


@pytest.mark.usefixtures("_window_org")
def test_factory_builds_the_requested_tier_with_the_requested_window() -> None:
    backend = memory_backend_for("window", 3)
    assert isinstance(backend, WindowBackend)
    assert backend._window == 3
    assert isinstance(memory_backend_for("summary", None), SummaryBackend)


@pytest.mark.usefixtures("_window_org")
def test_factory_caches_per_pair() -> None:
    assert memory_backend_for("window", 3) is memory_backend_for("window", 3)
    assert memory_backend_for("window", 3) is not memory_backend_for("window", 5)


@pytest.mark.usefixtures("_window_org")
def test_factory_applies_a_bare_window_to_the_org_tier() -> None:
    backend = memory_backend_for(None, 4)
    assert isinstance(backend, WindowBackend)
    assert backend._window == 4


# --------------------------------------------------------------------------- #
# The reporter — the state's knobs pick the backend
# --------------------------------------------------------------------------- #


class _CaptureBackend:
    name = "capture"
    model = "capture-model"

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    async def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        self.kwargs = kwargs
        return ChatResponse(
            content="ok", model=self.model, input_tokens=1, output_tokens=1, finish_reason="stop"
        )


def _chat_state(user_input: str) -> AgentState:
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=user_input,
        language=LanguageCode.FR,
        language_confidence=1.0,
    )


@pytest.mark.usefixtures("_window_org")
async def test_reporter_resolves_its_backend_from_the_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _factory(tier: str | None = None, window: int | None = None) -> WindowBackend:
        captured["args"] = (tier, window)
        return WindowBackend(history_window=2)

    monkeypatch.setattr(reporter, "memory_backend_for", _factory)
    llm = _CaptureBackend()
    monkeypatch.setattr(reporter, "backend_for_model", lambda _m: llm)
    state = _chat_state("Bonjour")
    state["memory"] = {"tier": "summary", "window": 4}
    await reporter._synthesise(cast("AgentState", state))
    assert captured["args"] == ("summary", 4)


@pytest.mark.usefixtures("_window_org")
async def test_reporter_off_seam_uses_the_org_singleton(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def _factory(tier: str | None = None, window: int | None = None) -> WindowBackend:
        captured["args"] = (tier, window)
        return WindowBackend(history_window=2)

    monkeypatch.setattr(reporter, "memory_backend_for", _factory)
    llm = _CaptureBackend()
    monkeypatch.setattr(reporter, "backend_for_model", lambda _m: llm)
    await reporter._synthesise(cast("AgentState", _chat_state("Bonjour")))
    assert captured["args"] == (None, None)

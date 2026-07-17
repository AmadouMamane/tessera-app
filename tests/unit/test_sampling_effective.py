"""ADR 0031 — sampling parameters are effective by construction.

Five witnesses, each interrogating the THING (ADR 0026), so the sliders can
never quietly go back to being cosmetic:

* the resolver returns the runtime truth — temperature 0.2, set-only extras,
  fail-open on a corrupt store;
* the chat ROUTE puts the store's sampling into the graph's initial state
  (captured inside ``ainvoke``, where the real graph reads it);
* the reporter's synthesis call passes the seam-resolved sampling to the
  backend — captured at the backend call, never read off a display field;
* each backend forwards exactly what ``SAMPLING_APPLIED`` declares for it —
  asserted on the kwargs handed to the underlying client;
* the declaration itself matches the real backend names.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest

from tessera.agent import reporter
from tessera.agent.state import AgentState, new_state
from tessera.llm.frontier import VertexAIBackend, _generation_config
from tessera.llm.local import OllamaBackend
from tessera.llm.openai_backend import OpenAIBackend
from tessera.llm.router import SAMPLING_APPLIED, ChatMessage, ChatResponse
from tessera.memory import get_memory_backend
from tessera.observability import agent_configurations as configurations
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


# --------------------------------------------------------------------------- #
# The resolver — runtime truth, set-only, fail-open
# --------------------------------------------------------------------------- #


def test_resolve_sampling_default_is_the_runtime_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    """No override → exactly {temperature: 0.2}: what the reporter always sent."""
    monkeypatch.setattr(configurations, "_load_overrides", lambda *_a: {})
    assert configurations.resolve_sampling("support-client") == {"temperature": 0.2}


def test_resolve_sampling_returns_only_set_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset parameter is ABSENT — never a fabricated number for the backend."""
    monkeypatch.setattr(
        configurations, "_load_overrides", lambda *_a: {"temperature": 0.7, "top_p": 0.9}
    )
    assert configurations.resolve_sampling("recouvrement") == {"temperature": 0.7, "top_p": 0.9}


def test_resolve_sampling_unset_temperature_resolves_to_runtime_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit reset (stored None) serves the runtime default, not nothing."""
    monkeypatch.setattr(configurations, "_load_overrides", lambda *_a: {"temperature": None})
    assert configurations.resolve_sampling() == {"temperature": 0.2}


def test_resolve_sampling_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A corrupt store can never take the chat path down — and it says so."""

    def _boom(*_a: object) -> dict[str, object]:
        msg = "store corrupt"
        raise RuntimeError(msg)

    monkeypatch.setattr(configurations, "_effective", _boom)
    assert configurations.resolve_sampling() == {"temperature": 0.2}
    assert "resolve_sampling" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# The route seam — the graph's initial state carries the store's sampling
# --------------------------------------------------------------------------- #


def test_chat_route_puts_store_sampling_into_the_graph_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /chat resolves sampling at the routing seam and hands it to the graph.

    The witness reads the state INSIDE ``ainvoke`` — where the real graph (and
    the reporter below it) observes it — then stops the turn without an LLM.
    """
    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    monkeypatch.setattr(
        configurations, "_load_overrides", lambda *_a: {"temperature": 0.65, "top_p": 0.85}
    )

    class _ProbeGraph:
        def __init__(self) -> None:
            self.sampling: object = None

        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            self.sampling = state.get("sampling")
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
    assert probe.sampling == {"temperature": 0.65, "top_p": 0.85}


# --------------------------------------------------------------------------- #
# The reporter — the seam-resolved sampling reaches the backend call
# --------------------------------------------------------------------------- #


@pytest.fixture
def _window_backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Hermetic Tier-0 memory backend (the dev .env.local would reach Postgres)."""
    monkeypatch.setenv("TESSERA_MEMORY__BACKEND", "window")
    get_settings.cache_clear()
    get_memory_backend.cache_clear()
    yield
    get_settings.cache_clear()
    get_memory_backend.cache_clear()


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


@pytest.mark.usefixtures("_window_backend")
async def test_reporter_passes_the_seam_sampling_to_the_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CaptureBackend()
    monkeypatch.setattr(reporter, "backend_for_model", lambda _m: backend)
    state = _chat_state("Quels sont vos horaires ?")
    state["sampling"] = {"temperature": 0.7, "top_p": 0.9}
    await reporter._synthesise(cast("AgentState", state))
    assert backend.kwargs is not None
    assert backend.kwargs["temperature"] == 0.7
    assert backend.kwargs["top_p"] == 0.9
    assert backend.kwargs["frequency_penalty"] is None
    assert backend.kwargs["presence_penalty"] is None


@pytest.mark.usefixtures("_window_backend")
async def test_reporter_defaults_when_the_seam_never_ran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A state without the seam's sampling serves the historical 0.2, nothing else."""
    backend = _CaptureBackend()
    monkeypatch.setattr(reporter, "backend_for_model", lambda _m: backend)
    await reporter._synthesise(cast("AgentState", _chat_state("Bonjour")))
    assert backend.kwargs is not None
    assert backend.kwargs["temperature"] == 0.2
    assert backend.kwargs["top_p"] is None


# --------------------------------------------------------------------------- #
# The backends — each forwards exactly what it declares (SAMPLING_APPLIED)
# --------------------------------------------------------------------------- #


async def test_ollama_forwards_exactly_the_set_parameters() -> None:
    """Ollama applies all four — and an unset one is NOT in the options dict."""
    captured: dict[str, Any] = {}

    class _FakeClient:
        async def chat(self, **kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {
                "message": {"content": "ok"},
                "prompt_eval_count": 1,
                "eval_count": 1,
                "done_reason": "stop",
            }

    backend = object.__new__(OllamaBackend)
    backend.model = "test-model"
    backend._keep_alive = "60s"
    backend._client = _FakeClient()  # type: ignore[assignment]
    messages = [ChatMessage(role="user", content="hi")]

    await OllamaBackend.chat(
        backend, messages, temperature=0.7, top_p=0.9, frequency_penalty=0.5, presence_penalty=0.1
    )
    assert captured["options"] == {
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.1,
    }

    captured.clear()
    await OllamaBackend.chat(backend, messages, temperature=0.2)
    assert captured["options"] == {"temperature": 0.2}


def test_vertex_generation_config_sends_top_p_only_when_set() -> None:
    """Vertex applies temperature + top-p; an unset top-p is not sent at all.

    The penalties have no path into ``_generation_config`` by design — the
    signature marks them unused and ``SAMPLING_APPLIED`` declares it.
    """
    assert _generation_config(0.2, None, 100) == {"temperature": 0.2, "max_output_tokens": 100}
    assert _generation_config(0.4, 0.9, 100) == {
        "temperature": 0.4,
        "top_p": 0.9,
        "max_output_tokens": 100,
    }


async def test_openai_never_forwards_sampling() -> None:
    """The OpenAI backend forwards NO sampling kwargs — reasoning models reject them."""
    captured: dict[str, Any] = {}

    class _FakeCompletions:
        async def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            from types import SimpleNamespace

            return SimpleNamespace(
                choices=[
                    SimpleNamespace(message=SimpleNamespace(content="ok"), finish_reason="stop")
                ],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
            )

    backend = object.__new__(OpenAIBackend)
    backend.model = "gpt-5.5"
    from types import SimpleNamespace

    backend._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=_FakeCompletions())
    )
    await OpenAIBackend.chat(
        backend,
        [ChatMessage(role="user", content="hi")],
        temperature=0.9,
        top_p=0.9,
        frequency_penalty=1.0,
        presence_penalty=1.0,
    )
    forbidden = {"temperature", "top_p", "frequency_penalty", "presence_penalty"}
    assert forbidden.isdisjoint(captured), f"sampling leaked to OpenAI: {sorted(captured)}"


def test_the_declaration_matches_the_real_backend_names() -> None:
    """SAMPLING_APPLIED is keyed by the backends' real names — no phantom entry."""
    assert set(SAMPLING_APPLIED) == {"ollama", "vertex-ai", "openai"}
    assert OllamaBackend.name == "ollama"
    assert VertexAIBackend.name == "vertex-ai"
    assert OpenAIBackend.name == "openai"
    assert set(SAMPLING_APPLIED["ollama"]) == {
        "temperature",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
    }
    assert set(SAMPLING_APPLIED["vertex-ai"]) == {"temperature", "top_p"}
    assert SAMPLING_APPLIED["openai"] == ()

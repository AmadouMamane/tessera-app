"""ADR 0032 — the behaviour selects are effective by construction.

Same witness discipline as ADR 0031 (``test_sampling_effective.py``), each
interrogating the THING (ADR 0026), so Ton / Détail / Longueur max can never
quietly go back to being cosmetic:

* the resolver returns the directive slugs and the declared token budget from
  the same effective configuration the page displays — fail-open, loudly;
* the chat ROUTE puts style + hard cap into the graph's initial state
  (captured inside ``ainvoke``, where the real graph reads it);
* the reporter appends the bundle's directives to the system prompt — and a
  console ``system_prompt_override`` stays verbatim (no style block);
* the reporter passes the hard cap and top-k to the backend call;
* every language bundle carries the complete directive set, and every slug the
  resolver can emit has a directive in every bundle — a missing translation is
  red, never silently English.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import pytest

from tessera.agent import reporter
from tessera.agent.state import AgentState, new_state
from tessera.llm.router import ChatMessage, ChatResponse
from tessera.memory import get_memory_backend
from tessera.observability import agent_configurations as configurations
from tessera.settings import LanguageCode, get_settings

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence


# --------------------------------------------------------------------------- #
# The resolver — slugs + declared budget, same read as the page
# --------------------------------------------------------------------------- #


def test_resolve_style_default_is_the_declared_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """No override → the stored defaults, as slugs, and the Moyenne budget."""
    monkeypatch.setattr(configurations, "_load_overrides", lambda *_a: {})
    style, budget = configurations.resolve_style("support-client")
    assert style == {"tone": "professionnel", "detail": "equilibre", "length": "moyenne"}
    assert budget == 2048


def test_resolve_style_follows_the_stored_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """An override changes the slug AND the budget — one read, two effects."""
    monkeypatch.setattr(
        configurations,
        "_load_overrides",
        lambda *_a: {"tone": "Amical", "detail": "Détaillé", "max_length": "Courte"},
    )
    style, budget = configurations.resolve_style("recouvrement")
    assert style == {"tone": "amical", "detail": "detaille", "length": "courte"}
    assert budget == 512


def test_resolve_style_fails_open_loudly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A corrupt store can never take the chat path down — and it says so."""

    def _boom(*_a: object) -> dict[str, object]:
        msg = "store corrupt"
        raise RuntimeError(msg)

    monkeypatch.setattr(configurations, "_effective", _boom)
    style, budget = configurations.resolve_style()
    assert style == {"tone": "professionnel", "detail": "equilibre", "length": "moyenne"}
    assert budget == 2048
    assert "resolve_style" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# The route seam — the graph's initial state carries style + hard cap
# --------------------------------------------------------------------------- #


def test_chat_route_puts_style_and_cap_into_the_graph_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /chat resolves the behaviour selects at the routing seam.

    The witness reads the state INSIDE ``ainvoke`` — where the real graph (and
    the reporter below it) observes it — then stops the turn without an LLM.
    """
    from starlette.testclient import TestClient

    from tessera.api.main import build_app
    from tessera.api.routes import chat as chat_route

    monkeypatch.setattr(
        configurations, "_load_overrides", lambda *_a: {"tone": "Direct", "max_length": "Longue"}
    )

    class _ProbeGraph:
        def __init__(self) -> None:
            self.style: object = None
            self.max_output_tokens: object = None

        async def ainvoke(self, state: dict[str, Any], config: object = None) -> object:
            self.style = state.get("style")
            self.max_output_tokens = state.get("max_output_tokens")
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
    assert probe.style == {"tone": "direct", "detail": "equilibre", "length": "longue"}
    assert probe.max_output_tokens == 8192


# --------------------------------------------------------------------------- #
# The reporter — directives reach the system prompt; the cap reaches the call
# --------------------------------------------------------------------------- #


def _chat_state(user_input: str) -> AgentState:
    return new_state(
        conversation_id=uuid.uuid4(),
        turn_id=uuid.uuid4(),
        user_input=user_input,
        language=LanguageCode.FR,
        language_confidence=1.0,
    )


def test_style_directives_are_injected_from_the_bundle() -> None:
    """The seam-resolved style becomes the bundle's directives — no Python text."""
    prompts = reporter.load_prompts(LanguageCode.FR)
    state = _chat_state("Bonjour")
    state["style"] = {"tone": "amical", "detail": "concis", "length": "courte"}
    system_prompt, _ = reporter._build_synthesis_input(cast("AgentState", state), prompts)
    assert prompts["style_header"].strip() in system_prompt
    assert prompts["tone_directive_amical"].strip() in system_prompt
    assert prompts["detail_directive_concis"].strip() in system_prompt
    assert prompts["length_directive_courte"].strip() in system_prompt


def test_no_style_means_no_style_block() -> None:
    """A path that never crossed the seam keeps the historical prompt."""
    prompts = reporter.load_prompts(LanguageCode.FR)
    state = _chat_state("Bonjour")
    system_prompt, _ = reporter._build_synthesis_input(cast("AgentState", state), prompts)
    assert prompts["style_header"].strip() not in system_prompt


def test_a_console_override_stays_verbatim() -> None:
    """ADR 0032 §4 — an operator probing a raw prompt gets the raw prompt."""
    prompts = reporter.load_prompts(LanguageCode.FR)
    state = _chat_state("Bonjour")
    state["style"] = {"tone": "amical", "detail": "concis", "length": "courte"}
    state["system_prompt_override"] = "PROMPT EXACT DU BAC A SABLE"
    system_prompt, _ = reporter._build_synthesis_input(cast("AgentState", state), prompts)
    assert system_prompt == "PROMPT EXACT DU BAC A SABLE"


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


@pytest.mark.usefixtures("_window_backend")
async def test_reporter_passes_the_hard_cap_and_top_k_to_the_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CaptureBackend()
    monkeypatch.setattr(reporter, "backend_for_model", lambda _m: backend)
    state = _chat_state("Quels sont vos horaires ?")
    state["sampling"] = {"temperature": 0.2, "top_k": 40.0}
    state["max_output_tokens"] = 512
    await reporter._synthesise(cast("AgentState", state))
    assert backend.kwargs is not None
    assert backend.kwargs["top_k"] == 40.0
    assert backend.kwargs["max_output_tokens"] == 512


@pytest.mark.usefixtures("_window_backend")
async def test_reporter_sends_no_cap_when_the_seam_never_ran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical behaviour off the seam: no cap beyond the backend's own default."""
    backend = _CaptureBackend()
    monkeypatch.setattr(reporter, "backend_for_model", lambda _m: backend)
    await reporter._synthesise(cast("AgentState", _chat_state("Bonjour")))
    assert backend.kwargs is not None
    assert backend.kwargs["max_output_tokens"] is None
    assert backend.kwargs["top_k"] is None


# --------------------------------------------------------------------------- #
# The bundles — complete in all three languages, coherent with the resolver
# --------------------------------------------------------------------------- #

_STYLE_KEYS = (
    "style_header",
    "tone_directive_professionnel",
    "tone_directive_amical",
    "tone_directive_direct",
    "tone_directive_pedagogique",
    "detail_directive_concis",
    "detail_directive_equilibre",
    "detail_directive_detaille",
    "length_directive_courte",
    "length_directive_moyenne",
    "length_directive_longue",
)


@pytest.mark.parametrize("language", [LanguageCode.FR, LanguageCode.DE, LanguageCode.EN])
def test_every_bundle_carries_the_complete_directive_set(language: LanguageCode) -> None:
    prompts = reporter.load_prompts(language)
    for key in _STYLE_KEYS:
        assert prompts.get(key, "").strip(), f"{language.value}.yaml is missing {key}"


def test_every_resolver_slug_has_a_directive_in_every_bundle() -> None:
    """Coherence: what the resolver can emit, every bundle can render.

    Interrogates the real mappings (``_STYLE_SLUGS``, ``_OPTIONS``,
    ``_LENGTH_BUDGET_TOKENS``) against the real YAML files — a new option value
    without its directive (or its budget) is red before it ships.
    """
    for language in (LanguageCode.FR, LanguageCode.DE, LanguageCode.EN):
        prompts = reporter.load_prompts(language)
        for value in configurations._OPTIONS["tone"]:
            key = f"tone_directive_{configurations._STYLE_SLUGS[value]}"
            assert prompts.get(key, "").strip(), f"{language.value}: missing {key}"
        for value in configurations._OPTIONS["detail"]:
            key = f"detail_directive_{configurations._STYLE_SLUGS[value]}"
            assert prompts.get(key, "").strip(), f"{language.value}: missing {key}"
        for value in configurations._OPTIONS["max_length"]:
            key = f"length_directive_{configurations._STYLE_SLUGS[value]}"
            assert prompts.get(key, "").strip(), f"{language.value}: missing {key}"
            assert value in configurations._LENGTH_BUDGET_TOKENS, f"no budget for {value}"

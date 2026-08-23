"""ADR 0053 slice 3 — the LLM understands in SHADOW, and the declaration matches the thing.

Three planes of witness: the A5 declaration (llm_structured + an existing referent that
names the agent), the classifier itself (schema-valid verdict or a failure that names its
kind — never an exception into the caller), and the shadow seam (a declared intent spawns
nothing; a classified turn records the comparison in the ledger under its own turn).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import TYPE_CHECKING

import pytest

from eval.intent_bench import DEFAULT_SET_PATH, load_intent_set
from tessera.agent.agentspec import UnderstandingMode, UnderstandingSpec
from tessera.agent.registry import get_agent
from tessera.api.routes import recouvrement_assistant
from tessera.llm.router import ChatResponse
from tessera.observability import business_events as business_events_mod
from tessera.recouvrement.understanding import (
    UnderstandingOutcome,
    UnderstandingVerdict,
    classify_intent_llm,
    intent_vocabulary,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tessera.llm.router import ChatMessage


# ── A5: the declaration, and the declaration against the thing ──────────────────────────


def test_recouvrement_declares_llm_structured_understanding() -> None:
    """The manifest names the understanding ruler: llm_structured over the labeled set."""
    spec = get_agent("recouvrement").observability
    assert spec is not None
    assert spec.understanding is not None
    assert spec.understanding.mode is UnderstandingMode.LLM_STRUCTURED
    assert spec.understanding.bench_set == "recouvrement"


def test_declared_bench_set_exists_and_names_the_declaring_agent() -> None:
    """The referent the manifest points at exists on disk and is about this agent."""
    spec = get_agent("recouvrement").observability
    assert spec is not None and spec.understanding is not None
    bench_set = spec.understanding.bench_set
    assert bench_set is not None
    assert DEFAULT_SET_PATH.name == f"{bench_set}.json"
    assert load_intent_set().agent_id == "recouvrement"


def test_llm_structured_without_bench_set_is_refused_at_load() -> None:
    """An LLM understanding without a labeled referent is unverifiable — refused (A5.2)."""
    with pytest.raises(ValueError, match="requires bench_set"):
        UnderstandingSpec(mode=UnderstandingMode.LLM_STRUCTURED)


def test_the_declaring_agents_turn_route_wires_the_shadow_seam() -> None:
    """The declaration is held to the wiring: the message route spawns the shadow (ADR 0026)."""
    source = inspect.getsource(recouvrement_assistant.recouvrement_assistant_message)
    assert "_spawn_shadow_understanding" in source


def test_classifier_vocabulary_is_the_manifest_vocabulary() -> None:
    """The closed vocabulary is read from the registry, never a copied list."""
    spec = get_agent("recouvrement").observability
    assert spec is not None
    assert intent_vocabulary() == {capability.id for capability in spec.capabilities}


# ── the classifier: a verdict or a failure that names its kind ─────────────────────────


class _FakeBackend:
    """A ChatBackend double answering with a canned body."""

    name = "fake"
    model = "fake-model"

    def __init__(self, content: str) -> None:
        self._content = content

    async def chat(self, messages: Sequence[ChatMessage], **_: object) -> ChatResponse:
        return ChatResponse(
            content=self._content,
            model=self.model,
            input_tokens=10,
            output_tokens=10,
            finish_reason="stop",
        )


def _wire_fake_backend(monkeypatch: pytest.MonkeyPatch, content: str) -> None:
    from tessera.llm import ceiling, router

    async def _no_ceiling(*, caller: str, model: str | None = None) -> str:
        return model or "fake-model"

    monkeypatch.setattr(ceiling, "resolve_spend_model", _no_ceiling)
    monkeypatch.setattr(router, "get_chat_backend", lambda: _FakeBackend(content))


async def test_classifier_returns_a_schema_valid_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean JSON answer inside the vocabulary becomes a verdict outcome."""
    body = json.dumps(
        {
            "intent": "propose_schedule",
            "confidence": 0.91,
            "duration_months": 6,
            "requested_time": None,
        }
    )
    _wire_fake_backend(monkeypatch, f"Here you go:\n```json\n{body}\n```")
    outcome = await classify_intent_llm("Propose un échéancier sur 6 mois", language="fr")
    assert outcome.status == "verdict"
    assert outcome.verdict == UnderstandingVerdict(
        intent="propose_schedule", confidence=0.91, duration_months=6, requested_time=None
    )
    assert outcome.model == "fake-model"
    assert outcome.prompt_version == "recouvrement_intent.v1"


async def test_classifier_refuses_an_intent_outside_the_vocabulary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A confident answer naming a capability the manifest does not declare is invalid."""
    body = json.dumps({"intent": "transfer_money", "confidence": 0.99})
    _wire_fake_backend(monkeypatch, body)
    outcome = await classify_intent_llm("vire l'argent", language="fr")
    assert outcome.status == "schema_invalid"
    assert outcome.verdict is None
    assert outcome.detail is not None and "outside the manifest vocabulary" in outcome.detail


async def test_classifier_names_garbage_as_schema_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prose instead of JSON is a named failure, never an exception into the caller."""
    _wire_fake_backend(monkeypatch, "Je pense que c'est un échéancier.")
    outcome = await classify_intent_llm("peu importe", language="fr")
    assert outcome.status == "schema_invalid"


async def test_classifier_timeout_is_a_named_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A model slower than the bound comes back as 'timeout', with the model named."""
    from tessera.llm import ceiling, router

    async def _no_ceiling(*, caller: str, model: str | None = None) -> str:
        return "slow-model"

    class _SlowBackend(_FakeBackend):
        async def chat(self, messages: Sequence[ChatMessage], **_: object) -> ChatResponse:
            await asyncio.sleep(30)
            raise AssertionError("unreachable")

    monkeypatch.setattr(ceiling, "resolve_spend_model", _no_ceiling)
    monkeypatch.setattr(router, "get_chat_backend", lambda: _SlowBackend(""))
    outcome = await classify_intent_llm("n'importe", language="fr", timeout_s=0.05)
    assert outcome.status == "timeout"
    assert outcome.model == "slow-model"


# ── the shadow seam: skip declared, record classified, record failures as themselves ────


@pytest.fixture
def _memory_ledger() -> None:
    business_events_mod.set_business_event_store(business_events_mod.InMemoryBusinessEventStore())


def _fake_result(intent_source: str, intent: str = "summarize_case") -> dict[str, object]:
    """A minimal route result carrying the rows the spawn reads its identifiers from."""
    return {
        "decisions": {"intent": intent},
        "businessEvents": [
            {
                "event_name": "intent.routed",
                "payload": {"intent_source": intent_source},
                "surface": "dedicated-ui",
                "conversation_id": "conv-shadow",
                "turn_id": "turn-shadow",
                "environment": "dev",
            }
        ],
    }


def _payload(language: str = "fr") -> recouvrement_assistant.RecouvrementAssistantRequest:
    return recouvrement_assistant.RecouvrementAssistantRequest(
        case_id="RC-2048",
        message="Où en est-on sur ce dossier ?",
        language=language,  # type: ignore[arg-type]
    )


async def _drain_shadow_tasks() -> None:
    while recouvrement_assistant._SHADOW_TASKS:
        await asyncio.gather(*tuple(recouvrement_assistant._SHADOW_TASKS))


async def test_a_declared_intent_spawns_no_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pressed button is an answer; the classifier has nothing to add."""
    called = False

    async def _classify(message: str, **_: object) -> UnderstandingOutcome:
        nonlocal called
        called = True
        raise AssertionError("unreachable")

    monkeypatch.setattr(recouvrement_assistant, "classify_intent_llm", _classify)
    recouvrement_assistant._spawn_shadow_understanding(_payload(), _fake_result("declared"))
    await _drain_shadow_tasks()
    assert called is False


async def test_a_classified_turn_records_the_comparison_under_its_own_turn(
    monkeypatch: pytest.MonkeyPatch, _memory_ledger: None
) -> None:
    """The shadow row joins the exact turn it shadows, and says whether the two agree."""

    async def _classify(message: str, **_: object) -> UnderstandingOutcome:
        return UnderstandingOutcome(
            status="verdict",
            verdict=UnderstandingVerdict(
                intent="summarize_case", confidence=0.88, duration_months=None, requested_time=None
            ),
            detail=None,
            model="fake-model",
            prompt_version="recouvrement_intent.v1",
            latency_ms=12.0,
        )

    monkeypatch.setattr(recouvrement_assistant, "classify_intent_llm", _classify)
    recouvrement_assistant._spawn_shadow_understanding(_payload(), _fake_result("regex"))
    await _drain_shadow_tasks()
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-shadow", turn_id="turn-shadow"
    )
    shadow_rows = [row for row in rows if row.get("node_name") == "shadow_understanding"]
    assert len(shadow_rows) == 1
    payload = shadow_rows[0]["payload"]
    assert payload["shadow"] is True
    assert payload["schema_valid"] is True
    assert payload["llm_intent"] == "summarize_case"
    assert payload["routed_intent"] == "summarize_case"
    assert payload["agree"] is True
    assert payload["prompt_version"] == "recouvrement_intent.v1"


async def test_a_failed_classification_is_recorded_as_its_kind(
    monkeypatch: pytest.MonkeyPatch, _memory_ledger: None
) -> None:
    """A timeout in the shadow is telemetry, not silence: status named, agreement unknown."""

    async def _classify(message: str, **_: object) -> UnderstandingOutcome:
        return UnderstandingOutcome(
            status="timeout",
            verdict=None,
            detail="no answer within 8.0s",
            model="slow-model",
            prompt_version="recouvrement_intent.v1",
            latency_ms=8000.0,
        )

    monkeypatch.setattr(recouvrement_assistant, "classify_intent_llm", _classify)
    recouvrement_assistant._spawn_shadow_understanding(_payload(), _fake_result("regex"))
    await _drain_shadow_tasks()
    rows = business_events_mod.business_event_rows(
        agent_id="recouvrement", conversation_id="conv-shadow", turn_id="turn-shadow"
    )
    payload = next(row for row in rows if row.get("node_name") == "shadow_understanding")["payload"]
    assert payload["llm_status"] == "timeout"
    assert payload["schema_valid"] is False
    assert payload["agree"] is None
    assert payload["llm_intent"] is None

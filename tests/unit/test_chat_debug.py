"""Unit tests for the console Debug surfaces built on the chat turn.end envelope.

These lock the eight live introspection surfaces (prompt / memory / routing /
usage / reviewer / language / draft / config) added to ``_debug_from_state``,
and the indicative cost estimator they rely on. Real data only — every value
must trace to the agent state, never a fabricated default.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from tessera.agent.supervisor import RoutingDecision
from tessera.api.routes.chat import _debug_from_state, _debug_trace
from tessera.llm.budget import estimate_turn_cost
from tessera.settings import LanguageCode

if TYPE_CHECKING:
    import pytest


def _state() -> dict[str, object]:
    """A representative streaming-synthesis turn state."""
    return {
        "language": LanguageCode.FR,
        "language_confidence": 1.0,
        "plan": ["regulation_lookup", "product_lookup"],
        "plan_rationale": "Question réglementaire + produit.",
        "confidence": 0.75,
        "grounding_score": 0.5,
        "coverage_score": 1.0,
        "guard_score": 1.0,
        "needs_escalation": False,
        "input_tokens": 2207,
        "output_tokens": 258,
        "model": "gpt-5.5",
        "system_prompt_override": "Tu es un agent de test.",
        "guard_overrides": ["pii"],
        "draft_response": "",
        "debug_prompt_messages": [
            {"role": "system", "content": "You are a banking assistant."},
            {"role": "user", "content": "Quels sont les frais ?"},
        ],
        "debug_memory": {
            "summary": "Résumé antérieur.",
            "entities": ["1 250 €", "FR76..."],
            "long_term": ["Le client préfère le français."],
            "recent_verbatim": 2,
            "backend": "PersistentBackend",
        },
    }


def _decision() -> RoutingDecision:
    return RoutingDecision(
        agent_id="support-client", handoff=False, from_agent=None, reason="stay->support-client"
    )


def _debug() -> dict[str, object]:
    return _debug_from_state(
        state=_state(),
        timings={"reporter": 4936.0},
        starts={"reporter": 0.0},
        citations=[],
        final_response="Les frais de tenue de compte sont de 0 €.",
        decision=_decision(),
        latency_ms=4936.6,
        pinned_language=True,
    )


def test_all_eight_surfaces_present() -> None:
    debug = _debug()
    for key in ("prompt", "memory", "routing", "usage", "reviewer", "language", "draft", "config"):
        assert key in debug, f"missing debug surface: {key}"


def test_prompt_surface_reflects_assembled_messages() -> None:
    prompt = _debug()["prompt"]
    assert isinstance(prompt, dict)
    assert prompt["message_count"] == 2
    messages = prompt["messages"]
    assert isinstance(messages, list)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert prompt["char_count"] == sum(len(m["content"]) for m in messages)


def test_memory_surface_flattens_real_context() -> None:
    memory = _debug()["memory"]
    assert isinstance(memory, dict)
    assert memory["backend"] == "PersistentBackend"
    assert memory["recent_verbatim"] == 2
    assert memory["entities"] == ["1 250 €", "FR76..."]
    assert memory["long_term"] == ["Le client préfère le français."]


def test_routing_surface_carries_decision_and_plan() -> None:
    routing = _debug()["routing"]
    assert isinstance(routing, dict)
    assert routing["agent_id"] == "support-client"
    assert routing["handoff"] is False
    assert routing["plan"] == ["regulation_lookup", "product_lookup"]
    assert routing["plan_rationale"] == "Question réglementaire + produit."


def test_usage_surface_uses_real_tokens_and_estimated_cost() -> None:
    usage = _debug()["usage"]
    assert isinstance(usage, dict)
    assert usage["input_tokens"] == 2207
    assert usage["output_tokens"] == 258
    assert usage["total_tokens"] == 2465
    # gpt-5.5 is a known frontier model → a non-zero indicative cost.
    assert usage["provider"] == "openai"
    assert usage["estimated_cost_eur"] > 0.0


def test_reviewer_surface_exposes_subscore_split() -> None:
    reviewer = _debug()["reviewer"]
    assert isinstance(reviewer, dict)
    assert reviewer["confidence"] == 0.75
    assert reviewer["grounding"] == 0.5
    assert reviewer["coverage"] == 1.0
    assert reviewer["guard"] == 1.0
    assert reviewer["needs_escalation"] is False


def test_language_and_draft_and_config_surfaces() -> None:
    debug = _debug()
    language = debug["language"]
    assert isinstance(language, dict)
    assert language["detected"] == "fr"
    assert language["pinned"] is True

    draft = debug["draft"]
    assert isinstance(draft, dict)
    assert draft["changed"] is True  # empty worker draft vs a real final answer
    assert draft["draft_label"] == "Aucun brouillon"  # no raw synthesis, empty worker draft
    assert draft["final_chars"] == len("Les frais de tenue de compte sont de 0 €.")

    config = debug["config"]
    assert isinstance(config, dict)
    assert config["model"] == "gpt-5.5"
    assert config["model_source"] == "override"
    assert config["system_prompt_override"] is True
    assert config["guard_overrides"] == ["pii"]


def test_prompt_and_memory_absent_without_synthesis() -> None:
    """An escalation/injection-block turn never calls the LLM → no prompt/memory."""
    state = _state()
    del state["debug_prompt_messages"]
    del state["debug_memory"]
    debug = _debug_from_state(
        state=state,
        timings={},
        starts={},
        citations=[],
        final_response="Escaladé vers un conseiller.",
        decision=_decision(),
        latency_ms=12.0,
        pinned_language=False,
    )
    assert "prompt" not in debug
    assert "memory" not in debug
    # The always-on surfaces still render.
    assert "routing" in debug
    assert "usage" in debug


def test_quality_panel_uses_real_reviewer_scores_not_fabrication() -> None:
    """The quality headline must scale the reviewer's real axes (no 0.78 fallback,
    no cosmetic formulas)."""
    quality = _debug()["quality"]
    assert isinstance(quality, dict)
    assert quality["badge"] == "Bon"  # needs_escalation is False in the fixture
    rows = {r["label"]: r["value"] for r in quality["rows"]}  # type: ignore[union-attr]
    # confidence 0.75 → 7.5, grounding 0.5 → 5.0, coverage 1.0 → 10.0, guard → 10.0
    assert rows == {
        "Confiance": "7.5",
        "Ancrage": "5.0",
        "Couverture": "10.0",
        "Securite": "10.0",
    }


def test_quality_badge_reflects_real_escalation() -> None:
    state = _state()
    state["needs_escalation"] = True
    debug = _debug_from_state(
        state=state,
        timings={},
        starts={},
        citations=[],
        final_response="Escaladé.",
        decision=_decision(),
        latency_ms=10.0,
        pinned_language=True,
    )
    quality = debug["quality"]
    assert isinstance(quality, dict)
    assert quality["badge"] == "A surveiller"
    assert quality["badge_tone"] == "warn"


def test_draft_prefers_raw_synthesis_and_shows_stripping() -> None:
    state = _state()
    state["debug_synthesis_raw"] = "<think>raisonnement interne</think>Réponse finale."
    debug = _debug_from_state(
        state=state,
        timings={},
        starts={},
        citations=[],
        final_response="Réponse finale.",
        decision=_decision(),
        latency_ms=10.0,
        pinned_language=True,
    )
    draft = debug["draft"]
    assert isinstance(draft, dict)
    assert draft["draft_label"] == "Synthèse brute (avant nettoyage)"
    assert "<think>" in str(draft["draft"])  # the stripped reasoning is visible here
    assert draft["final"] == "Réponse finale."
    assert draft["changed"] is True


def test_trace_appends_reporter_span_so_total_reconciles_with_latency() -> None:
    """The reporter streams after the graph pauses (interrupt_before) and is not in
    the Phase-1 node timings; the trace must append it so the total matches the
    turn's wall-clock latency instead of stopping at the lookups."""
    timings = {"product_lookup": 185.0, "regulation_lookup": 231.0}
    starts = {"product_lookup": 4.0, "regulation_lookup": 20.0}
    # Phase-1 ends at max(start+dur) = 20 + 231 = 251.0.
    without = _debug_trace(timings, starts)
    assert without["total_ms"] == 251.0
    assert "reporter" not in [s["key"] for s in without["spans"]]  # type: ignore[index,union-attr]

    with_reporter = _debug_trace(timings, starts, reporter_ms=5267.0)
    spans = with_reporter["spans"]
    assert isinstance(spans, list)
    reporter = spans[-1]
    assert reporter["key"] == "reporter"
    assert reporter["start_ms"] == 251.0  # starts where Phase 1 ends
    assert reporter["duration_ms"] == 5267.0
    # Total now reconciles with the real latency, not the lookups alone.
    assert with_reporter["total_ms"] == 251.0 + 5267.0


def test_estimate_turn_cost_resolves_provider_by_model() -> None:
    assert estimate_turn_cost(model="gpt-5.5", input_tokens=1000, output_tokens=0)[0] == "openai"
    assert (
        estimate_turn_cost(model="gemini-2.0-flash-001", input_tokens=1000, output_tokens=0)[0]
        == "vertex-ai"
    )
    # Unknown (small local) model → on-prem, zero marginal cost.
    provider, cost = estimate_turn_cost(model="llama3.2:3b", input_tokens=5000, output_tokens=500)
    assert provider == "ollama"
    assert cost == Decimal(0)


# ---------------------------------------------------------------------------
# XT-01 — the S2 capture seam. The turn state holds the assembled prompt, the
# resolved sampling and the tool records; the seam must thread them into the
# replay bundle rather than drop them at the capture boundary.


def test_the_capture_helpers_read_the_real_state() -> None:
    from tessera.agent.state import ToolCallRecord
    from tessera.api.routes.chat import (
        _capture_prompt_messages,
        _capture_sampling,
        _capture_tool_calls,
    )

    state = _state()
    state["sampling"] = {"temperature": 0.3, "top_p": 0.9}
    state["tool_calls"] = [
        ToolCallRecord(
            tool_name="loan_simulate",
            node="simulator",
            arguments={"amount": 1000},
            result={"ok": True},
            succeeded=True,
            duration_ms=12.34,
        )
    ]
    assert _capture_prompt_messages(state) == [
        {"role": "system", "content": "You are a banking assistant."},
        {"role": "user", "content": "Quels sont les frais ?"},
    ]
    assert _capture_sampling(state) == {"temperature": 0.3, "top_p": 0.9}
    # Arguments and results never reach the record — they can carry PII.
    assert _capture_tool_calls(state) == [
        {"name": "loan_simulate", "node": "simulator", "succeeded": True, "duration_ms": 12.3}
    ]


def test_the_capture_helpers_say_none_when_nothing_was_recorded() -> None:
    from tessera.api.routes.chat import (
        _capture_prompt_messages,
        _capture_sampling,
        _capture_tool_calls,
    )

    empty: dict[str, object] = {}
    assert _capture_prompt_messages(empty) is None
    assert _capture_sampling(empty) is None
    assert _capture_tool_calls(empty) is None


def test_the_online_eval_seam_threads_the_s2_record_into_the_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    import uuid as uuid_mod
    from types import SimpleNamespace

    from tessera.api.routes import chat as chat_module
    from tessera.observability import replay as replay_module
    from tessera.observability.eval import online as online_eval

    async def _stub_evaluate_turn(**_kwargs: object) -> object:
        return SimpleNamespace(verdict=SimpleNamespace(score=0.8))

    captured: dict[str, object] = {}

    def _record_capture(**kwargs: object) -> object:
        captured.update(kwargs)
        return SimpleNamespace(bundle_id="recorded")

    # chat.py binds these modules by name; patching the module OBJECTS reaches
    # the names chat.py holds (a `from x import y` copies the reference).
    monkeypatch.setattr(online_eval, "evaluate_turn", _stub_evaluate_turn)
    monkeypatch.setattr(replay_module, "capture_bundle", _record_capture)

    conversation_id = uuid_mod.uuid4()
    turn_id = uuid_mod.uuid4()
    asyncio.run(
        chat_module._run_online_eval(
            question="q",
            answer="a",
            context="c",
            language=LanguageCode.FR,
            conversation_id=conversation_id,
            model="m",
            agent_id="support-client",
            turn_id=turn_id,
            prompt_messages=[{"role": "user", "content": "q"}],
            sampling={"temperature": 0.2},
            max_output_tokens=256,
            tool_calls=[
                {
                    "name": "card_block",
                    "node": "account_lookup",
                    "succeeded": True,
                    "duration_ms": 3.0,
                }
            ],
            node_starts={"router": 0.0},
            reporter_ms=421.0,
        )
    )
    assert captured["turn_id"] == str(turn_id)
    assert captured["prompt_messages"] == [{"role": "user", "content": "q"}]
    assert captured["sampling"] == {"temperature": 0.2}
    assert captured["max_output_tokens"] == 256
    assert captured["tool_calls"] == [
        {"name": "card_block", "node": "account_lookup", "succeeded": True, "duration_ms": 3.0}
    ]
    assert captured["node_starts"] == {"router": 0.0}
    assert captured["reporter_ms"] == 421.0

"""Unit tests for node/tool span instrumentation (ADR 0010, Phase 2, #4)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tessera.observability import instrument, semconv
from tessera.settings import LanguageCode


@pytest.fixture
def in_memory_spans(monkeypatch: pytest.MonkeyPatch) -> InMemorySpanExporter:
    """Route instrumentation spans into an in-memory exporter."""
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("test")
    monkeypatch.setattr(instrument, "tracer", lambda *_a, **_k: test_tracer)
    return exporter


def test_instrument_node_emits_invoke_agent_span(in_memory_spans: InMemorySpanExporter) -> None:
    async def fake_run(state: dict[str, Any]) -> dict[str, object]:
        return {"draft_response": "ok"}

    wrapped = instrument.instrument_node("regulation_lookup", fake_run)
    result = asyncio.run(wrapped({"language": LanguageCode.FR}))

    assert result == {"draft_response": "ok"}
    span = in_memory_spans.get_finished_spans()[0]
    assert span.name == "invoke_agent regulation_lookup"
    assert span.attributes is not None
    assert span.attributes[semconv.GEN_AI_OPERATION_NAME] == semconv.GenAIOperation.INVOKE_AGENT
    assert span.attributes[semconv.GEN_AI_AGENT_NAME] == "regulation_lookup"
    assert span.attributes[semconv.TESSERA_LANGUAGE] == LanguageCode.FR.value


def test_instrument_node_records_error_count(in_memory_spans: InMemorySpanExporter) -> None:
    async def failing_run(state: dict[str, Any]) -> dict[str, object]:
        return {"errors": ["boom", "bang"]}

    wrapped = instrument.instrument_node("account_lookup", failing_run)
    asyncio.run(wrapped({"language": LanguageCode.EN}))

    span = in_memory_spans.get_finished_spans()[0]
    assert span.attributes is not None
    assert span.attributes["tessera.node.error_count"] == 2


def test_instrument_node_omits_language_when_absent(in_memory_spans: InMemorySpanExporter) -> None:
    async def fake_run(state: dict[str, Any]) -> dict[str, object]:
        return {}

    wrapped = instrument.instrument_node("router", fake_run)
    asyncio.run(wrapped({}))

    span = in_memory_spans.get_finished_spans()[0]
    assert span.attributes is not None
    assert semconv.TESSERA_LANGUAGE not in span.attributes


def test_tool_span_emits_execute_tool_span(in_memory_spans: InMemorySpanExporter) -> None:
    with instrument.tool_span("account_balance", LanguageCode.DE) as span:
        span.set_attribute(semconv.TESSERA_GUARD_DECISION, "allowed")

    span_data = in_memory_spans.get_finished_spans()[0]
    assert span_data.name == "execute_tool account_balance"
    assert span_data.attributes is not None
    assert (
        span_data.attributes[semconv.GEN_AI_OPERATION_NAME] == semconv.GenAIOperation.EXECUTE_TOOL
    )
    assert span_data.attributes[semconv.GEN_AI_TOOL_NAME] == "account_balance"
    assert span_data.attributes[semconv.TESSERA_LANGUAGE] == LanguageCode.DE.value
    assert span_data.attributes[semconv.TESSERA_GUARD_DECISION] == "allowed"


def test_collect_node_timings_records_duration(in_memory_spans: InMemorySpanExporter) -> None:
    async def fake_run(state: dict[str, Any]) -> dict[str, object]:
        return {}

    wrapped = instrument.instrument_node("slow_node", fake_run)
    with instrument.collect_node_timings() as timings:
        asyncio.run(wrapped({"language": LanguageCode.FR}))

    assert "slow_node" in timings
    assert timings["slow_node"] >= 0.0


def test_retrieval_span_records_cited_categories(in_memory_spans: InMemorySpanExporter) -> None:
    with instrument.retrieval_span("credit_aurore", LanguageCode.FR) as span:
        instrument.annotate_retrieval(
            span, categories=["cartes", "comptes"], hit_count=5, top_score=0.81
        )

    span_data = in_memory_spans.get_finished_spans()[0]
    assert span_data.name == "retrieve credit_aurore"
    assert span_data.attributes is not None
    assert span_data.attributes[semconv.OPENINFERENCE_SPAN_KIND] == "RETRIEVER"
    assert span_data.attributes[semconv.TESSERA_RETRIEVAL_CORPUS] == "credit_aurore"
    assert span_data.attributes[semconv.TESSERA_RETRIEVAL_CATEGORIES] == "cartes,comptes"
    assert span_data.attributes[semconv.TESSERA_RETRIEVAL_HIT_COUNT] == 5
    assert span_data.attributes[semconv.TESSERA_RETRIEVAL_TOP_SCORE] == pytest.approx(0.81)
    assert span_data.attributes[semconv.TESSERA_LANGUAGE] == LanguageCode.FR.value


def test_retrieval_span_omits_language_when_none(in_memory_spans: InMemorySpanExporter) -> None:
    with instrument.retrieval_span("regulations", None) as span:
        instrument.annotate_retrieval(span, categories=[], hit_count=0, top_score=None)

    span_data = in_memory_spans.get_finished_spans()[0]
    assert span_data.attributes is not None
    # No cited categories -> empty string (still queryable), no top_score, no language.
    assert span_data.attributes[semconv.TESSERA_RETRIEVAL_CATEGORIES] == ""
    assert span_data.attributes[semconv.TESSERA_RETRIEVAL_HIT_COUNT] == 0
    assert semconv.TESSERA_RETRIEVAL_TOP_SCORE not in span_data.attributes
    assert semconv.TESSERA_LANGUAGE not in span_data.attributes

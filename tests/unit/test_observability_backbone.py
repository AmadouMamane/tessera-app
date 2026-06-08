"""Unit tests for the OTel gen_ai observability backbone (ADR 0010, Phase 1)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tessera.observability import semconv, traces


class _RecordingSpan:
    """Duck-typed stand-in for an OTel span that records calls."""

    def __init__(self) -> None:
        self.attributes: dict[str, Any] = {}
        self.events: list[tuple[str, dict[str, Any]]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append((name, attributes or {}))


# ── semconv: span names ───────────────────────────────────────────────────────


def test_agent_span_name_follows_operation_target_convention() -> None:
    assert semconv.agent_span_name("regulation_lookup") == "invoke_agent regulation_lookup"


def test_tool_span_name_follows_operation_target_convention() -> None:
    assert semconv.tool_span_name("account_balance") == "execute_tool account_balance"


# ── semconv: request / usage attributes ───────────────────────────────────────


def test_set_gen_ai_request_sets_standard_attributes() -> None:
    span = _RecordingSpan()
    semconv.set_gen_ai_request(span, system="ollama", model="llama3.3:70b", temperature=0.2)
    assert span.attributes[semconv.GEN_AI_SYSTEM] == "ollama"
    assert span.attributes[semconv.GEN_AI_REQUEST_MODEL] == "llama3.3:70b"
    assert span.attributes[semconv.GEN_AI_OPERATION_NAME] == semconv.GenAIOperation.CHAT
    assert span.attributes[semconv.GEN_AI_REQUEST_TEMPERATURE] == pytest.approx(0.2)


def test_set_gen_ai_request_omits_temperature_when_none() -> None:
    span = _RecordingSpan()
    semconv.set_gen_ai_request(span, system="vertex_ai", model="gemini")
    assert semconv.GEN_AI_REQUEST_TEMPERATURE not in span.attributes


def test_set_gen_ai_usage_sets_token_counts() -> None:
    span = _RecordingSpan()
    semconv.set_gen_ai_usage(span, input_tokens=128, output_tokens=42, response_model="m")
    assert span.attributes[semconv.GEN_AI_USAGE_INPUT_TOKENS] == 128
    assert span.attributes[semconv.GEN_AI_USAGE_OUTPUT_TOKENS] == 42
    assert span.attributes[semconv.GEN_AI_RESPONSE_MODEL] == "m"


# ── semconv: content capture gating (PII) ──────────────────────────────────────


def test_add_content_event_records_body_when_capture_enabled() -> None:
    span = _RecordingSpan()
    semconv.add_content_event(span, role="user", content="solde du compte", capture=True)
    name, attrs = span.events[0]
    assert name == "gen_ai.user.message"
    assert attrs["content"] == "solde du compte"


def test_add_content_event_redacts_body_when_capture_disabled() -> None:
    span = _RecordingSpan()
    semconv.add_content_event(span, role="assistant", content="FR76 3000 4000", capture=False)
    name, attrs = span.events[0]
    assert name == "gen_ai.assistant.message"
    assert attrs["content.redacted"] is True
    assert attrs["content.length"] == len("FR76 3000 4000")
    assert "content" not in attrs


# ── traces: profile-driven exporter selection ──────────────────────────────────


def _fake_obs(**overrides: Any) -> SimpleNamespace:
    base = {
        "profile": "on_prem",
        "cloud_logging_project": None,
        "otel_collector_endpoint": None,
        "otel_endpoint": None,
    }
    base.update(overrides)
    return SimpleNamespace(observability=SimpleNamespace(**base))


def test_resolve_exporter_uses_collector_endpoint_on_prem(monkeypatch: pytest.MonkeyPatch) -> None:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    monkeypatch.setattr(
        traces, "get_settings", lambda: _fake_obs(otel_collector_endpoint="http://localhost:4418")
    )
    assert isinstance(traces._resolve_exporter(), OTLPSpanExporter)


def test_resolve_exporter_falls_back_to_legacy_otel_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    monkeypatch.setattr(
        traces, "get_settings", lambda: _fake_obs(otel_endpoint="http://collector:4318")
    )
    assert isinstance(traces._resolve_exporter(), OTLPSpanExporter)


def test_resolve_exporter_console_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter

    monkeypatch.setattr(traces, "get_settings", lambda: _fake_obs())
    assert isinstance(traces._resolve_exporter(), ConsoleSpanExporter)


def test_resolve_exporter_gcp_without_project_falls_through_to_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    monkeypatch.setattr(
        traces,
        "get_settings",
        lambda: _fake_obs(profile="gcp", otel_collector_endpoint="http://localhost:4418"),
    )
    assert isinstance(traces._resolve_exporter(), OTLPSpanExporter)


def test_resolve_exporter_appends_v1_traces_to_bare_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        traces, "get_settings", lambda: _fake_obs(otel_collector_endpoint="http://localhost:4418")
    )
    exporter = traces._resolve_exporter()
    assert exporter._endpoint == "http://localhost:4418/v1/traces"  # type: ignore[attr-defined]


def test_resolve_exporter_keeps_explicit_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        traces,
        "get_settings",
        lambda: _fake_obs(otel_collector_endpoint="http://localhost:4418/v1/traces"),
    )
    exporter = traces._resolve_exporter()
    assert exporter._endpoint == "http://localhost:4418/v1/traces"  # type: ignore[attr-defined]

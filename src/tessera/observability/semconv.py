"""OpenTelemetry GenAI semantic conventions for Tessera (ADR 0010).

This module is the vendor-neutral *backbone* of the observability layer. Code
across the agent emits spans carrying these ``gen_ai.*`` attributes; the
OpenTelemetry Collector then routes them to whichever backend the deployment
profile selects (Phoenix / Langfuse on-prem, Cloud Trace on GCP). Nothing here
depends on a backend — that is the whole point.

We pin the attribute *names* to the official OpenTelemetry GenAI semantic
conventions (``gen_ai.*``) and define them as constants rather than importing
from ``opentelemetry.semconv`` so a churning incubating spec cannot break the
build. Tessera-domain attributes live under the ``tessera.*`` namespace.

The agent-span operations (``invoke_agent`` / ``execute_tool`` / ``chat``)
follow the GenAI *agent* span conventions, so a LangGraph node and an
LLM-callable tool produce spans a generic OTel backend understands.

References:
    * OpenTelemetry GenAI semantic conventions (``gen_ai.*``), incl. the
      experimental agent spans ``invoke_agent`` / ``execute_tool`` /
      ``create_agent``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from opentelemetry.trace import Span

__all__ = [
    "GEN_AI_AGENT_NAME",
    "GEN_AI_CONVERSATION_ID",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_REQUEST_TEMPERATURE",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_TOOL_NAME",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "TESSERA_DATA_RESIDENCY",
    "TESSERA_GUARD_DECISION",
    "TESSERA_GUARD_RULE",
    "TESSERA_LANGUAGE",
    "TESSERA_PROFILE",
    "GenAIOperation",
    "add_content_event",
    "agent_span_name",
    "set_gen_ai_request",
    "set_gen_ai_usage",
    "tool_span_name",
]

# ── gen_ai.* attribute keys (official OTel GenAI semconv) ─────────────────────
GEN_AI_SYSTEM: Final = "gen_ai.system"
GEN_AI_OPERATION_NAME: Final = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL: Final = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE: Final = "gen_ai.request.temperature"
GEN_AI_RESPONSE_MODEL: Final = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS: Final = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS: Final = "gen_ai.usage.output_tokens"
GEN_AI_AGENT_NAME: Final = "gen_ai.agent.name"
GEN_AI_TOOL_NAME: Final = "gen_ai.tool.name"
GEN_AI_CONVERSATION_ID: Final = "gen_ai.conversation.id"

# ── tessera.* domain attribute keys ──────────────────────────────────────────
TESSERA_LANGUAGE: Final = "tessera.language"
TESSERA_PROFILE: Final = "tessera.profile"
TESSERA_DATA_RESIDENCY: Final = "tessera.data_residency"
TESSERA_GUARD_DECISION: Final = "tessera.guard.decision"
TESSERA_GUARD_RULE: Final = "tessera.guard.rule"


class GenAIOperation:
    """GenAI span operation names (``gen_ai.operation.name`` values).

    These mirror the operations defined by the OpenTelemetry GenAI agent span
    conventions. They are grouped on a class purely as a typed namespace.
    """

    CHAT: Final = "chat"
    EMBEDDINGS: Final = "embeddings"
    INVOKE_AGENT: Final = "invoke_agent"
    EXECUTE_TOOL: Final = "execute_tool"
    CREATE_AGENT: Final = "create_agent"


def agent_span_name(agent_name: str) -> str:
    """Return the span name for invoking an agent/worker node.

    Follows the GenAI convention ``"{operation} {target}"``, e.g.
    ``"invoke_agent regulation_lookup"``.

    Args:
        agent_name: The LangGraph node / worker name.

    Returns:
        The conventional span name.
    """
    return f"{GenAIOperation.INVOKE_AGENT} {agent_name}"


def tool_span_name(tool_name: str) -> str:
    """Return the span name for executing an LLM-callable tool.

    Follows the GenAI convention ``"{operation} {target}"``, e.g.
    ``"execute_tool account_balance"``.

    Args:
        tool_name: The tool name.

    Returns:
        The conventional span name.
    """
    return f"{GenAIOperation.EXECUTE_TOOL} {tool_name}"


def set_gen_ai_request(
    span: Span,
    *,
    system: str,
    model: str,
    operation: str = GenAIOperation.CHAT,
    temperature: float | None = None,
) -> None:
    """Attach the standard ``gen_ai.*`` request attributes to ``span``.

    Args:
        span: The active span to annotate.
        system: The GenAI system (e.g. ``"ollama"``, ``"vertex_ai"``).
        model: The requested model id.
        operation: The ``gen_ai.operation.name`` value.
        temperature: Sampling temperature, when known.
    """
    span.set_attribute(GEN_AI_SYSTEM, system)
    span.set_attribute(GEN_AI_OPERATION_NAME, operation)
    span.set_attribute(GEN_AI_REQUEST_MODEL, model)
    if temperature is not None:
        span.set_attribute(GEN_AI_REQUEST_TEMPERATURE, temperature)


def set_gen_ai_usage(
    span: Span,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    response_model: str | None = None,
) -> None:
    """Attach the standard ``gen_ai.*`` usage/response attributes to ``span``.

    Args:
        span: The active span to annotate.
        input_tokens: Prompt token count, when known.
        output_tokens: Completion token count, when known.
        response_model: The model that actually served the response.
    """
    if input_tokens is not None:
        span.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
    if output_tokens is not None:
        span.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)
    if response_model is not None:
        span.set_attribute(GEN_AI_RESPONSE_MODEL, response_model)


def add_content_event(
    span: Span,
    *,
    role: str,
    content: str,
    capture: bool,
) -> None:
    """Record prompt/completion content as a span event, PII-gated.

    Following the OTel GenAI direction, message content is recorded as a span
    *event* rather than a high-cardinality attribute. The body is only attached
    when ``capture`` is true (``ObservabilitySettings.content_capture``);
    otherwise a redacted marker is recorded so the trace still shows that a
    message occurred without leaking its content. This is the in-process
    complement to the Collector-side redaction (ADR 0010, ideas #3/#4).

    Args:
        span: The active span to annotate.
        role: The message role (``"user"``, ``"assistant"``, ``"system"``).
        content: The message content.
        capture: Whether content capture is enabled for this deployment.
    """
    event_name = f"gen_ai.{role}.message"
    if capture:
        span.add_event(event_name, attributes={"content": content})
    else:
        span.add_event(
            event_name,
            attributes={"content.redacted": True, "content.length": len(content)},
        )

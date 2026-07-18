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
    from collections.abc import Mapping

    from opentelemetry.trace import Span

__all__ = [
    "CONDITIONAL_TURN_SPAN_ATTRIBUTES",
    "DEPLOYMENT_ENVIRONMENT",
    "GEN_AI_AGENT_NAME",
    "GEN_AI_CONVERSATION_ID",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_REQUEST_FREQUENCY_PENALTY",
    "GEN_AI_REQUEST_MAX_TOKENS",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_REQUEST_PRESENCE_PENALTY",
    "GEN_AI_REQUEST_TEMPERATURE",
    "GEN_AI_REQUEST_TOP_K",
    "GEN_AI_REQUEST_TOP_P",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_SYSTEM",
    "GEN_AI_TOOL_NAME",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "OPENINFERENCE_SPAN_KIND",
    "REQUIRED_TURN_SPAN_ATTRIBUTES",
    "TESSERA_AGENT_ID",
    "TESSERA_ARTIFACT_ID",
    "TESSERA_ARTIFACT_STATUS",
    "TESSERA_ARTIFACT_TYPE",
    "TESSERA_BUDGET_OVERRUN",
    "TESSERA_CASE_ID",
    "TESSERA_DATA_RESIDENCY",
    "TESSERA_ESCALATION_THRESHOLD",
    "TESSERA_GUARD_DECISION",
    "TESSERA_GUARD_RULE",
    "TESSERA_LANGUAGE",
    "TESSERA_PROFILE",
    "TESSERA_RETRIEVAL_CATEGORIES",
    "TESSERA_RETRIEVAL_CORPUS",
    "TESSERA_RETRIEVAL_HIT_COUNT",
    "TESSERA_RETRIEVAL_TOP_SCORE",
    "TESSERA_STORE",
    "TESSERA_STORE_OPERATION",
    "TESSERA_STORE_ROWS",
    "TESSERA_STORE_TARGET",
    "TESSERA_SYNTHETIC",
    "TESSERA_TURN_ID",
    "TESSERA_WORKFLOW_ID",
    "GenAIOperation",
    "add_content_event",
    "agent_span_name",
    "retrieval_span_name",
    "set_gen_ai_request",
    "set_gen_ai_usage",
    "stamp_turn_dimensions",
    "stamp_turn_sampling",
    "tool_span_name",
]

# ── gen_ai.* attribute keys (official OTel GenAI semconv) ─────────────────────
GEN_AI_SYSTEM: Final = "gen_ai.system"
GEN_AI_OPERATION_NAME: Final = "gen_ai.operation.name"
GEN_AI_REQUEST_MODEL: Final = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE: Final = "gen_ai.request.temperature"
GEN_AI_REQUEST_TOP_P: Final = "gen_ai.request.top_p"
GEN_AI_REQUEST_TOP_K: Final = "gen_ai.request.top_k"
GEN_AI_REQUEST_FREQUENCY_PENALTY: Final = "gen_ai.request.frequency_penalty"
GEN_AI_REQUEST_PRESENCE_PENALTY: Final = "gen_ai.request.presence_penalty"
GEN_AI_REQUEST_MAX_TOKENS: Final = "gen_ai.request.max_tokens"
GEN_AI_RESPONSE_MODEL: Final = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS: Final = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS: Final = "gen_ai.usage.output_tokens"
GEN_AI_AGENT_NAME: Final = "gen_ai.agent.name"
GEN_AI_TOOL_NAME: Final = "gen_ai.tool.name"
GEN_AI_CONVERSATION_ID: Final = "gen_ai.conversation.id"

# ── tessera.* domain attribute keys ──────────────────────────────────────────
TESSERA_LANGUAGE: Final = "tessera.language"
TESSERA_AGENT_ID: Final = "tessera.agent_id"
TESSERA_TURN_ID: Final = "tessera.turn_id"
TESSERA_WORKFLOW_ID: Final = "tessera.workflow_id"
TESSERA_CASE_ID: Final = "tessera.case_id"
TESSERA_ARTIFACT_ID: Final = "tessera.artifact_id"
TESSERA_ARTIFACT_TYPE: Final = "tessera.artifact_type"
TESSERA_ARTIFACT_STATUS: Final = "tessera.artifact_status"
#: The synthetic dimension on a span (ADR 0019 §4 · Amendment 1 A1.1). Stamped only on a
#: turn the platform declared synthetic — a Console test turn or a scheduled canary — so a
#: trace can be excluded from business reasoning without re-deriving who called whom. The
#: same single vocabulary as ``BusinessEvent.synthetic``; there is no parallel taxonomy.
TESSERA_SYNTHETIC: Final = "tessera.synthetic"
DEPLOYMENT_ENVIRONMENT: Final = "deployment.environment"
TESSERA_PROFILE: Final = "tessera.profile"
TESSERA_DATA_RESIDENCY: Final = "tessera.data_residency"
TESSERA_GUARD_DECISION: Final = "tessera.guard.decision"
TESSERA_GUARD_RULE: Final = "tessera.guard.rule"
# ADR 0033 — the escalation-confidence threshold that served the turn.
TESSERA_ESCALATION_THRESHOLD: Final = "tessera.escalation.threshold"
# ADR 0034 — the budget breaker's decision on this turn (block / local_fallback).
TESSERA_BUDGET_OVERRUN: Final = "tessera.budget.overrun"
# Retrieval spans (idea #4): which knowledge-source categories a real query
# actually retrieved above the citation threshold, so the citation rate per
# source can be read back from production telemetry rather than a synthetic probe.
TESSERA_RETRIEVAL_CORPUS: Final = "tessera.retrieval.corpus"
TESSERA_RETRIEVAL_CATEGORIES: Final = "tessera.retrieval.categories"
TESSERA_RETRIEVAL_HIT_COUNT: Final = "tessera.retrieval.hit_count"
TESSERA_RETRIEVAL_TOP_SCORE: Final = "tessera.retrieval.top_score"

# Control-plane store reads. The agent runtime was instrumented span by span; the cockpit that
# judges it emitted nothing, so its slowest endpoint was one span with zero children and not a
# millisecond of it was attributed to anything.
#: Which store a control-plane read touched: ``postgres`` / ``clickhouse`` / ``prometheus`` /
#: ``file``.
TESSERA_STORE: Final = "tessera.store"
#: The question, named — ``audit_ledger.payloads_all``, ``audit_ledger.latest_of_type_for_agent``.
TESSERA_STORE_OPERATION: Final = "tessera.store.operation"
#: The table / metric / file the read addressed.
TESSERA_STORE_TARGET: Final = "tessera.store.target"
#: HOW MANY ROWS CAME BACK — the field that carries the finding. A duration says a read was slow;
#: the row count says why, and it is the only one that makes six full 29 600-row scans legible as
#: six full scans rather than as one opaque four-second box. It counts rows MATERIALISED, not rows
#: scanned: an aggregate that groups 29 600 rows in the database and returns 29 is exactly the fix,
#: and must not read as the offence.
TESSERA_STORE_ROWS: Final = "tessera.store.rows"

# OpenInference span-kind hint so Phoenix renders the retrieval span as a
# retriever in its UI. Vendor-neutral backends simply ignore the extra attribute.
OPENINFERENCE_SPAN_KIND: Final = "openinference.span.kind"


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


def retrieval_span_name(corpus: str) -> str:
    """Return the span name for a retrieval query against a corpus.

    Follows the GenAI ``"{operation} {target}"`` shape, e.g. ``"retrieve
    regulations"``, so a generic OTel backend groups retrieval spans by corpus.

    Args:
        corpus: The corpus searched (e.g. ``"regulations"``, ``"credit_aurore"``).

    Returns:
        The conventional span name.
    """
    return f"retrieve {corpus}"


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


def stamp_turn_dimensions(
    span: Span,
    *,
    agent_id: str,
    language: str,
    model: str | None,
    conversation_id: str,
    turn_id: str,
    environment: str,
    synthetic: bool,
) -> None:
    """Stamp the full dimension set on a turn's root span (ADR 0015 §Migration B).

    Every fact-emitting path should carry the same dimensions; stamping them on the turn's
    root span makes the turn's trace queryable per {agent, language, model, conversation,
    turn, environment} — the substrate the spine reads (Langfuse ``metadata.agent_id``
    filter, per-dimension aggregates) and the cockpit slices by. Child spans nest under
    this one, so the trace as a whole is attributed.

    ``synthetic`` has no default on purpose (ADR 0019 §4): a caller that forgets to say
    whether the turn is a test turn would silently publish a test trace as product traffic,
    which is precisely the pollution §4 forbids. Stating it is the point.

    Args:
        span: The turn's root/active span.
        agent_id: The responding agent for the turn.
        language: The conversation language code (``fr``/``de``/``en``).
        model: The agent's serving model, when known.
        conversation_id: The conversation id (stable across turns).
        turn_id: The per-turn id.
        environment: The deployment environment (ADR 0014).
        synthetic: Whether this is a test turn (Console invocation or scheduled canary)
            rather than product traffic.
    """
    span.set_attribute(TESSERA_AGENT_ID, agent_id)
    span.set_attribute(TESSERA_LANGUAGE, language)
    span.set_attribute(GEN_AI_CONVERSATION_ID, conversation_id)
    span.set_attribute(TESSERA_TURN_ID, turn_id)
    span.set_attribute(DEPLOYMENT_ENVIRONMENT, environment)
    # Absent ⇒ false, exactly as on the wire (TurnInput.synthetic): one rule for both, so an
    # agent that predates the field keeps conforming and a product trace is never stamped.
    if synthetic:
        span.set_attribute(TESSERA_SYNTHETIC, True)
    if model:
        span.set_attribute(GEN_AI_REQUEST_MODEL, model)


#: The Scope dimensions a turn root span must ALWAYS carry (ADR 0015 §B / ADR 0017 §4
#: L1 span contract) — the single source of truth for the span-contract testkit
#: (signal 103) and the instrumentation-coverage descriptor (signal 92). It mirrors
#: exactly what ``stamp_turn_dimensions`` stamps unconditionally.
REQUIRED_TURN_SPAN_ATTRIBUTES: tuple[str, ...] = (
    TESSERA_AGENT_ID,
    TESSERA_LANGUAGE,
    GEN_AI_CONVERSATION_ID,
    TESSERA_TURN_ID,
    DEPLOYMENT_ENVIRONMENT,
)

#: Stamped only when a serving model is resolved for the turn (honest-absent otherwise).
CONDITIONAL_TURN_SPAN_ATTRIBUTES: tuple[str, ...] = (GEN_AI_REQUEST_MODEL,)


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


#: gen_ai.request.* key per sampling parameter (ADR 0031 — what serves is
#: what is recorded: only the parameters actually resolved for the turn are
#: stamped; an unset parameter is honest-absent, never a fabricated default).
_SAMPLING_ATTRIBUTE_KEYS: Final[dict[str, str]] = {
    "temperature": GEN_AI_REQUEST_TEMPERATURE,
    "top_p": GEN_AI_REQUEST_TOP_P,
    "top_k": GEN_AI_REQUEST_TOP_K,
    "frequency_penalty": GEN_AI_REQUEST_FREQUENCY_PENALTY,
    "presence_penalty": GEN_AI_REQUEST_PRESENCE_PENALTY,
}


def stamp_turn_sampling(
    span: Span, sampling: Mapping[str, float], *, max_output_tokens: int | None = None
) -> None:
    """Stamp the turn's resolved sampling parameters on its root span.

    Args:
        span: The turn's root span.
        sampling: The seam-resolved sampling (ADR 0031) — only SET parameters
            are present, and only those are stamped.
        max_output_tokens: The seam-resolved hard cap (ADR 0032), stamped as
            ``gen_ai.request.max_tokens`` when present.
    """
    for key, value in sampling.items():
        attribute = _SAMPLING_ATTRIBUTE_KEYS.get(key)
        if attribute is not None:
            span.set_attribute(attribute, value)
    if max_output_tokens is not None:
        span.set_attribute(GEN_AI_REQUEST_MAX_TOKENS, max_output_tokens)


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

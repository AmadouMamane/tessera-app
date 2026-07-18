"""Typed state passed between LangGraph nodes.

LangGraph identifies state by reducer functions on a ``TypedDict``. For
Tessera we use a single :class:`AgentState` with explicit reducers on the
fields that accumulate across nodes (messages, retrieved documents, tool
calls, guard decisions, citations), and last-write-wins on the scalar fields
that represent the agent's current best answer.

The state schema is the contract between the orchestration layer (graph) and
every node — keep it minimal, fully typed, and stable. New fields require a
mention in the relevant ADR.
"""

from __future__ import annotations

import contextlib
import operator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal, NotRequired, TypedDict
from uuid import UUID  # noqa: TCH003  — LangGraph calls get_type_hints() at runtime

from tessera.settings import LanguageCode  # noqa: TCH001  — same reason

__all__ = [
    "AgentState",
    "Citation",
    "ConversationMessage",
    "GuardDecisionRecord",
    "NodeName",
    "RetrievedDocument",
    "ToolCallRecord",
    "WorkerName",
    "new_state",
]


# ---------------------------------------------------------------------------
# Node identifiers
# ---------------------------------------------------------------------------


class NodeName(StrEnum):
    """Top-level LangGraph node identifiers.

    The values are also used as string keys when wiring the StateGraph and
    when emitting trace spans, so they must remain stable.
    """

    ROUTER = "router"
    PLANNER = "planner"
    DISPATCH = "dispatch"
    REVIEWER = "reviewer"
    REPORTER = "reporter"
    ESCALATION = "escalation"


class WorkerName(StrEnum):
    """Worker (orchestration) node identifiers."""

    PRODUCT_LOOKUP = "product_lookup"
    REGULATION_LOOKUP = "regulation_lookup"
    ACCOUNT_LOOKUP = "account_lookup"
    SIMULATOR = "simulator"
    ESCALATION = "escalation_worker"


# ---------------------------------------------------------------------------
# Frozen records carried in the state
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    """A single turn of the visible conversation."""

    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    name: str | None = None  # tool name when ``role == "tool"``


@dataclass(frozen=True, slots=True)
class RetrievedDocument:
    """A document chunk returned by the retrieval layer."""

    source: str
    chunk_id: str
    language: LanguageCode
    text: str
    score: float
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """An invocation of an LLM-callable tool, with its result."""

    tool_name: str
    arguments: dict[str, object]
    result: object | None
    succeeded: bool
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class GuardDecisionRecord:
    """One decision emitted by the runtime guard (first-party adapter)."""

    target: str  # tool or worker name being guarded
    decision: Literal["allow", "deny", "transform"]
    policy_rule: str
    rationale: str
    redactions: tuple[str, ...] = ()
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class Citation:
    """A regulatory or product-corpus citation used to ground a response."""

    source: str  # e.g. "DORA Article 28", "BaFin Rundschreiben 10/2022"
    locator: str  # e.g. "art. 28(3)", "section 4.2"
    language: LanguageCode
    excerpt: str


# ---------------------------------------------------------------------------
# Reducers for accumulating fields
# ---------------------------------------------------------------------------


def _dedup_concat[T](left: list[T], right: list[T]) -> list[T]:
    """Reducer that concatenates two lists, preserving order and removing duplicates by equality.

    Used for fields where two parallel workers may legitimately return the
    same document or citation — we keep the first occurrence to keep ordering
    deterministic for replay.
    """
    seen: set[int] = set()
    out: list[T] = []
    for item in (*left, *right):
        key = id(item) if not isinstance(item, str | int | float) else hash(item)
        # Frozen dataclasses are hashable; fall back to identity otherwise.
        with contextlib.suppress(TypeError):
            key = hash(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# The state itself
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    """The TypedDict passed between every LangGraph node.

    Fields annotated with ``Annotated[..., operator.add]`` accumulate across
    nodes; all others use LangGraph's default last-write-wins behaviour.
    """

    # --- Identity ---------------------------------------------------------
    conversation_id: UUID
    turn_id: UUID
    # Long-term memory subject key (ADR 0007). Defaults to str(conversation_id)
    # when the caller supplies no stable identifier.
    subject_id: NotRequired[str]

    # --- Input ------------------------------------------------------------
    user_input: str
    language: LanguageCode
    language_confidence: float
    # Optional per-request chat-model override (e.g. the UI model picker).
    # Falls back to the configured default (settings.ollama.chat_model).
    model: NotRequired[str]
    # ADR 0031 — per-turn sampling resolved at the routing seam from the
    # agent's effective configuration (only the SET parameters; temperature is
    # always present). The reporter passes it to the backend call, so the
    # slider value and the served value are the same read. Absent on paths
    # that never speak (escalation, injection block).
    sampling: NotRequired[dict[str, float]]
    # ADR 0032 — per-turn behaviour style resolved at the same seam
    # (tone/detail/length as ASCII directive slugs). The reporter appends the
    # matching prompt-bundle directives to the system prompt — unless a
    # system_prompt_override replaces the prompt verbatim.
    style: NotRequired[dict[str, str]]
    # ADR 0032 — the declared hard cap for the backend call (all three
    # backends apply it). Absent on paths that never cross the seam.
    max_output_tokens: NotRequired[int]
    # ADR 0033 — the escalation-confidence threshold resolved at the seam
    # (agent override, else the org settings value). The reviewer reads THIS;
    # paths that never cross the seam fall back to the settings.
    escalation_threshold: NotRequired[float]
    # ADR 0034 — set at the seam when the daily budget ceiling gates this
    # turn's paid model and the overrun behaviour is "block": the router
    # short-circuits the graph with the localized budget_exceeded message.
    budget_blocked: NotRequired[bool]
    # ADR 0035 — per-turn retrieval knobs resolved at the seam: "rerank"
    # (always present) and "top_k" (present only when set — absent means each
    # lookup worker's historical default serves). The lookup workers read THIS.
    retrieval: NotRequired[dict[str, object]]
    # --- Sandbox overrides (console playground) ---------------------------
    # Optional per-request system-prompt override; replaces the language
    # bundle's ``system`` prompt for this turn only (never persisted).
    system_prompt_override: NotRequired[str]
    # Guard categories disabled for this turn (e.g. ["prompt_injection",
    # "pii"]). Empty/absent = the full policy applies. Sandbox-only knob.
    guard_overrides: NotRequired[list[str]]

    # --- Conversation history --------------------------------------------
    messages: Annotated[list[ConversationMessage], operator.add]

    # --- Planning ---------------------------------------------------------
    plan: list[WorkerName]
    plan_rationale: NotRequired[str]

    # --- Retrieval --------------------------------------------------------
    retrieved_documents: Annotated[list[RetrievedDocument], _dedup_concat]

    # --- Tool use ---------------------------------------------------------
    tool_calls: Annotated[list[ToolCallRecord], operator.add]

    # --- Guardrails -------------------------------------------------------
    guard_decisions: Annotated[list[GuardDecisionRecord], operator.add]

    # --- Output -----------------------------------------------------------
    draft_response: NotRequired[str]
    final_response: NotRequired[str]
    confidence: NotRequired[float]
    citations: Annotated[list[Citation], _dedup_concat]

    # --- Reviewer sub-scores (console Debug surface) ----------------------
    # The reviewer fuses grounding/coverage/guard into ``confidence``; the
    # split is surfaced for the console's Debug tab. Written by the reviewer
    # node, read by the chat route's debug envelope.
    grounding_score: NotRequired[float]
    coverage_score: NotRequired[float]
    guard_score: NotRequired[float]

    # --- Debug capture (console Debug surface) ----------------------------
    # The reporter stashes the *exact* assembled LLM message list and the
    # injected memory context here so the chat route can surface them on the
    # turn.end event. Real data only — populated on the synthesis path.
    debug_prompt_messages: NotRequired[list[dict[str, str]]]
    debug_memory: NotRequired[dict[str, object]]
    # Raw (pre-strip) synthesis output, so the Debug "draft vs final" surface can
    # show what reasoning/markup was removed (e.g. a <think> block).
    debug_synthesis_raw: NotRequired[str]

    # --- Escalation -------------------------------------------------------
    needs_escalation: bool
    escalation_reason: NotRequired[str]

    # --- Usage ------------------------------------------------------------
    # Token accounting for the synthesis LLM call (0 when no LLM was invoked).
    input_tokens: NotRequired[int]
    output_tokens: NotRequired[int]

    # --- Error reporting --------------------------------------------------
    # Annotated so concurrent workers can each append without conflict.
    errors: Annotated[list[str], operator.add]


def new_state(
    *,
    conversation_id: UUID,
    turn_id: UUID,
    user_input: str,
    language: LanguageCode,
    language_confidence: float = 1.0,
    prior_messages: list[ConversationMessage] | None = None,
    subject_id: str | None = None,
    model: str | None = None,
    system_prompt_override: str | None = None,
    guard_overrides: list[str] | None = None,
) -> AgentState:
    """Construct a fresh :class:`AgentState` ready to enter the graph.

    Args:
        conversation_id: Stable identifier across multiple turns.
        turn_id: Identifier unique to this single turn.
        user_input: The raw user message in its detected language.
        language: The detected language (FR/DE/EN).
        language_confidence: Probability assigned by the language detector.
        prior_messages: Optional conversation history from previous turns.
            When provided, these messages are prepended so the reporter can
            inject multi-turn context into the LLM prompt.
        subject_id: Optional stable long-term-memory identity key. Defaults to
            ``str(conversation_id)`` (per-thread memory) when omitted.
        model: Optional per-request chat-model override; falls back to the
            configured default when omitted.
        system_prompt_override: Optional sandbox system-prompt override for
            this turn only; replaces the language bundle's ``system`` prompt.
        guard_overrides: Optional list of guard categories to disable for this
            turn (sandbox playground), e.g. ``["prompt_injection"]``.

    Returns:
        A state dict with all accumulator fields initialised to empty lists.
    """
    messages: list[ConversationMessage] = list(prior_messages or [])
    messages.append(ConversationMessage(role="user", content=user_input))
    state = AgentState(
        conversation_id=conversation_id,
        turn_id=turn_id,
        subject_id=subject_id or str(conversation_id),
        user_input=user_input,
        language=language,
        language_confidence=language_confidence,
        messages=messages,
        plan=[],
        retrieved_documents=[],
        tool_calls=[],
        guard_decisions=[],
        citations=[],
        needs_escalation=False,
        errors=[],
    )
    if model is not None:
        state["model"] = model
    if system_prompt_override is not None:
        state["system_prompt_override"] = system_prompt_override
    if guard_overrides:
        state["guard_overrides"] = guard_overrides
    return state

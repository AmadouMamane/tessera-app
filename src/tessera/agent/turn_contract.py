"""The assistant runtime turn contract (ADR 0018 §1).

One entry point per agent runtime — **the I/O of its LangGraph graph**, not a new
service layer. The state machine IS the graph; ``build_recouvrement_graph_v1`` is the
reference implementation. Runtime events ride the ADR 0016 envelope and the ADR 0017
workflow grammar — never a parallel event type.

Phase A of ADR 0018 *names* the contract without changing behaviour: the shipped
recouvrement output (``RecouvrementOutput``) conforms structurally — its keys are the
camelCase serialisation of :data:`TURN_RESULT_KEYS` consumed by the produit BFF. The
conformance is pinned by ``tests/unit/test_turn_contract_acceptance.py``; later phases
(enum codegen from AgentSpec capabilities, canonical artifact lifecycle) refactor the
*types*, not the UX.
"""

from __future__ import annotations

from typing import TypedDict

__all__ = [
    "TURN_RESULT_KEYS",
    "TurnAction",
    "TurnInput",
    "TurnResult",
]


class TurnAction(TypedDict, total=False):
    """A typed action dispatched by a UI button — never the button label as chat.

    ADR 0018 §2: buttons dispatch actions; free messages go through the intent router.
    ``type`` values are per-agent, derived from the AgentSpec capabilities (0017 §A1.1)
    — never a platform-wide union.
    """

    type: str
    case_id: str
    source_artifact_id: str
    params: dict[str, object]


class TurnInput(TypedDict, total=False):
    """What a turn consumes: stable case context + exactly one of message / action.

    ADR 0018 §7: the case context anchors every turn; the last user message never
    displaces it. ``active_task`` and artifact families are per-agent vocabularies.
    """

    case_id: str
    active_task: str
    user_message: str
    action: TurnAction
    artifacts: dict[str, object]
    conversation_id: str
    turn_id: str
    surface: str
    language: str
    #: Whether this turn is a *test* turn — a Console invocation or a scheduled canary —
    #: rather than product traffic (ADR 0019 §4, §Amendment 1 A1.1). Absent ⇒ ``False``,
    #: so every agent written before this field keeps conforming.
    #:
    #: Set **exclusively** by the platform's declared consumers of the invocation binding;
    #: product traffic never sets it. In-process, the equivalent mark is the
    #: ``synthetic_turn()`` ContextVar — a ContextVar cannot cross a process boundary,
    #: which is the whole reason this key exists.
    #:
    #: **Propagation duty (conformance, not advice).** An agent serving a turn with
    #: ``synthetic: true`` MUST stamp the synthetic dimension on every span, metric and
    #: business event it emits for that turn. Unpropagated synthetic traffic inflates
    #: business metrics until someone notices, so the SDK testkit gates it: see
    #: ``sdk.testkit.span_contract.verify_turn_span`` and
    #: ``sdk.testkit.grammar_conformance.verify_business_event``.
    synthetic: bool


class TurnResult(TypedDict, total=False):
    """What a turn produces. Artifacts are the source of truth; chat steers.

    Serialised camelCase for the produit BFF (``visibleReply``, ``cardUpdates``,
    ``suggestedActions``, ``businessEvents``, ``businessScores``). ``business_events``
    rows are ADR 0016 envelopes stamped with the ADR 0017 ``grammar_version``.
    """

    visible_reply: str
    artifact: dict[str, object] | None
    card_updates: list[dict[str, object]]
    suggested_actions: list[dict[str, object]]
    business_events: list[dict[str, object]]
    business_scores: list[dict[str, object]]
    decisions: dict[str, object]


#: The camelCase serialisation of :class:`TurnResult` that every agent runtime output
#: must carry (pinned by the acceptance suite — ADR 0018 §Acceptance criteria).
TURN_RESULT_KEYS: frozenset[str] = frozenset(
    {
        "visibleReply",
        "artifact",
        "cardUpdates",
        "suggestedActions",
        "businessEvents",
        "businessScores",
        "decisions",
    }
)

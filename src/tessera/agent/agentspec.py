"""AgentSpec v1 — the manifest ``observability`` block (ADR 0017 §3 + A1 + A2.3).

The registry entry (``agents.yaml``, ADR 0012) grows an ``observability`` block and
becomes the **AgentSpec**: one declarative artifact from which the cockpit's business
surfaces are *generated* (SignalSpec descriptors, the level badge, the Métier tab). A
manifest is an API, not config — every block is validated with ``extra="forbid"`` so a
typo is a load error, not a silently-dropped field (the same "make the illegal state
unrepresentable" move as the ADR 0015 registry, applied to the manifest).

Validation is a CI gate (``tests/unit/test_agentspec.py``); the loader
(:mod:`tessera.agent.registry`) raises :class:`ValueError` for any invalid block, so the
whole registry fails fast on a malformed manifest.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = [
    "AGENTSPEC_VERSION",
    "AgentObservabilitySpec",
    "BusinessMetricLevel",
    "BusinessSignalSource",
    "BusinessSignalSpec",
    "Capability",
    "ExternalEffectLevel",
    "InvocationAuth",
    "InvocationBinding",
    "InvocationSpec",
    "PolicyMetadata",
    "PolicySeverity",
    "QualityRegime",
    "SignalEngagement",
    "WorkflowBinding",
    "parse_invocation",
    "parse_observability",
    "validate_quality_seam",
]

#: The only AgentSpec version this build understands. A manifest declaring anything else
#: fails validation (explicit migrations, never silent best-effort parsing).
AGENTSPEC_VERSION = "agentspec.v1"


class ExternalEffectLevel(StrEnum):
    """How far a capability may reach outside the system (ADR 0017 §A1.1).

    A *static declaration* verified at runtime by the external-effect invariant (§A1.3);
    ``requires_validation`` / ``external_action`` are the levels that make an agent an
    L3-required candidate (§A2.4).
    """

    NONE = "none"
    DRAFT = "draft"
    REQUIRES_VALIDATION = "requires_validation"
    EXTERNAL_ACTION = "external_action"


class PolicySeverity(StrEnum):
    """Declared severity of a policy (ADR 0017 §A2.3)."""

    BLOCKING = "blocking"
    WARNING = "warning"


class BusinessSignalSource(StrEnum):
    """Where a declared business signal is read from (ADR 0017 §3)."""

    BUSINESS_SCORE = "business_score"
    BUSINESS_EVENT = "business_event"


class BusinessMetricLevel(StrEnum):
    """The 3-level business-metric ladder (ADR 0017 §A2.2)."""

    RUNTIME = "runtime"
    HUMAN_ACTION = "human_action"
    OUTCOME = "outcome"


class SignalEngagement(StrEnum):
    """Catalog engagement class — drives the Conformité projection (§6.4)."""

    SLO = "slo"
    GATE = "gate"
    LEGAL = "legal"
    SLA = "sla"
    NONE = "none"


class QualityRegime(StrEnum):
    """Which ruler judges this agent's production answers (ADR 0017 §3 Amendment 4).

    The cockpit runs TWO disjoint quality rulers — the online LLM judge
    (faithfulness/grounding/hallucination over the ``/chat`` seam) and deterministic
    business scorers (per-signal ``scored``/``unknown``/``not_applicable``) — and their
    populations must never share a denominator. The regime is **declared** by each agent,
    never inferred: an inference can drift silently when the schema evolves, a declaration
    is refused at load when it contradicts the rest of the manifest.

    ``unscored`` is a first-class declaration, not an absence: it names the blind spot and
    must carry its reason (ADR 0026 — a witness that cannot see reports a blind spot, never
    "ok").
    """

    LLM_JUDGED = "llm_judged"
    BUSINESS_SCORED = "business_scored"
    UNSCORED = "unscored"


class InvocationBinding(StrEnum):
    """How a declared consumer sends a turn to the agent (ADR 0019 §1).

    ``none`` is the honest default for publish-only agents — the Console renders honest-empty
    and no canary can drive it. ``in_process_chat`` *declares* the existing ``/chat`` seam
    (the three native agents adopt it verbatim — no behaviour change). ``http`` declares a
    turn endpoint the agent exposes speaking the 0018 turn contract; the invoker that forwards
    the operator assertion is I3, out of scope here — only the declaration is modelled.
    """

    NONE = "none"
    IN_PROCESS_CHAT = "in_process_chat"
    HTTP = "http"


class InvocationAuth(StrEnum):
    """Auth posture for an invocation (ADR 0019 §1/§4) — no anonymous invocation, ever."""

    OPERATOR_ASSERTION = "operator-assertion"


class _Spec(BaseModel):
    """A frozen, typo-proof manifest block: unknown keys are a validation error."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Capability(_Spec):
    """A typed business capability — the formalisation of ``active_task`` (§A1.1)."""

    id: str = Field(min_length=1)
    label_key: str = Field(min_length=1)
    input_schema: str | None = None
    output_artifacts: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()  # policy ids ONLY (implementations stay code — §A1.1)
    eval_packs: tuple[str, ...] = ()
    external_effect_level: ExternalEffectLevel = ExternalEffectLevel.NONE

    @field_validator("label_key")
    @classmethod
    def _capability_namespace(cls, value: str) -> str:
        if not value.startswith("capability."):
            msg = f"capability label_key must start with 'capability.': {value!r}"
            raise ValueError(msg)
        return value


class PolicyMetadata(_Spec):
    """Declared policy metadata — ids + reason codes only (§A2.3).

    Implementations stay deterministic code in the domain package; the manifest declares
    what the garde-fous tab renders without knowing the domain.
    """

    id: str = Field(min_length=1)
    label_key: str = Field(min_length=1)
    version: str = Field(min_length=1)
    severity: PolicySeverity
    applies_to: tuple[str, ...] = ()  # capability ids
    reason_codes: tuple[str, ...] = ()

    @field_validator("label_key")
    @classmethod
    def _policy_namespace(cls, value: str) -> str:
        if not value.startswith("policy."):
            msg = f"policy label_key must start with 'policy.': {value!r}"
            raise ValueError(msg)
        return value


class WorkflowBinding(_Spec):
    """A workflow the agent runs, mapped onto the versioned grammar (§2 + §3)."""

    workflow_id: str = Field(min_length=1)
    grammar: str = Field(min_length=1)
    scorer: str | None = None  # BusinessScoringRegistry id

    @field_validator("grammar")
    @classmethod
    def _grammar_namespace(cls, value: str) -> str:
        if not value.startswith("workflow_grammar."):
            msg = f"workflow grammar must start with 'workflow_grammar.': {value!r}"
            raise ValueError(msg)
        return value


class BusinessSignalSpec(_Spec):
    """A declared business KPI — generates a SignalSpec descriptor + surfaces (§3)."""

    key: str = Field(min_length=1)
    source: BusinessSignalSource
    level: BusinessMetricLevel
    unit: str = Field(min_length=1)
    aggregation: str = Field(min_length=1)
    dimensions: tuple[str, ...] = ()
    engagement: SignalEngagement = SignalEngagement.NONE
    north_star: bool = False

    @model_validator(mode="after")
    def _outcome_is_undeclarable(self) -> BusinessSignalSpec:
        # A2.2 display-honesty (binding): an ``outcome`` signal is undeclarable until a
        # real outcome feed exists (§A1.6) — the manifest validator rejects it, so no
        # fabricated real-world result can ever be presented as if it were measured.
        if self.level is BusinessMetricLevel.OUTCOME:
            msg = (
                f"business_signal {self.key!r}: level 'outcome' is undeclarable until a real "
                "outcome feed exists (ADR 0017 §A1.6 / §A2.2)"
            )
            raise ValueError(msg)
        return self


class AgentObservabilitySpec(_Spec):
    """The AgentSpec ``observability`` block (ADR 0017 §3)."""

    spec_version: str
    # The declared quality regime — REQUIRED, no default on purpose: a default would put a
    # ruler nobody chose behind an agent's quality figures (the ADR 0024 rule, applied to
    # judgment instead of authorship). ``unscored`` must name its reason through a locale
    # key so every surface can render the blind spot in the reader's language.
    quality_regime: QualityRegime
    quality_regime_reason_key: str | None = None
    telemetry_capabilities: tuple[str, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    policies: tuple[PolicyMetadata, ...] = ()
    workflows: tuple[WorkflowBinding, ...] = ()
    business_signals: tuple[BusinessSignalSpec, ...] = ()

    @field_validator("spec_version")
    @classmethod
    def _known_version(cls, value: str) -> str:
        if value != AGENTSPEC_VERSION:
            msg = f"unsupported AgentSpec spec_version {value!r}: expected {AGENTSPEC_VERSION!r}"
            raise ValueError(msg)
        return value

    @field_validator("quality_regime_reason_key")
    @classmethod
    def _reason_key_namespace(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith("quality_regime."):
            msg = f"quality_regime_reason_key must start with 'quality_regime.': {value!r}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _quality_regime_integrity(self) -> AgentObservabilitySpec:
        # A declared regime must be one the rest of the manifest can honour — the same
        # "make the illegal state unrepresentable" rule as the invocation block. The two
        # rulers stay disjoint by construction: declared business signals FORCE the
        # business_scored regime, so no scored plane can hide its ruler behind another.
        if self.quality_regime is QualityRegime.UNSCORED:
            if not self.quality_regime_reason_key:
                msg = (
                    "quality_regime 'unscored' requires quality_regime_reason_key — a blind "
                    "spot is declared with its reason, never silently (ADR 0026)"
                )
                raise ValueError(msg)
        elif self.quality_regime_reason_key is not None:
            msg = (
                f"quality_regime {self.quality_regime.value!r} must not set "
                "quality_regime_reason_key (a reason belongs to the declared blind spot only)"
            )
            raise ValueError(msg)
        if self.quality_regime is QualityRegime.BUSINESS_SCORED:
            if not self.business_signals:
                msg = (
                    "quality_regime 'business_scored' requires declared business_signals — "
                    "without them nothing would ever score this agent"
                )
                raise ValueError(msg)
            if not any(w.scorer for w in self.workflows):
                msg = (
                    "quality_regime 'business_scored' requires a workflow binding a scorer — "
                    "a ruler with no producer scores nothing"
                )
                raise ValueError(msg)
        elif self.business_signals:
            msg = (
                f"declared business_signals require quality_regime 'business_scored', "
                f"got {self.quality_regime.value!r} — a scored plane may not hide its ruler"
            )
            raise ValueError(msg)
        elif any(w.scorer for w in self.workflows):
            msg = (
                f"a workflow binding a scorer requires quality_regime 'business_scored', "
                f"got {self.quality_regime.value!r} — a producer forces its ruler's declaration"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _referential_integrity(self) -> AgentObservabilitySpec:
        cap_ids = [c.id for c in self.capabilities]
        if len(set(cap_ids)) != len(cap_ids):
            msg = "duplicate capability id in AgentSpec"
            raise ValueError(msg)
        pol_ids = [p.id for p in self.policies]
        if len(set(pol_ids)) != len(pol_ids):
            msg = "duplicate policy id in AgentSpec"
            raise ValueError(msg)
        cap_id_set, pol_id_set = set(cap_ids), set(pol_ids)
        for policy in self.policies:
            unknown = sorted(set(policy.applies_to) - cap_id_set)
            if unknown:
                msg = f"policy {policy.id!r} applies_to unknown capabilities {unknown}"
                raise ValueError(msg)
        for capability in self.capabilities:
            unknown = sorted(set(capability.policies) - pol_id_set)
            if unknown:
                msg = f"capability {capability.id!r} references unknown policies {unknown}"
                raise ValueError(msg)
        signal_keys = [s.key for s in self.business_signals]
        if len(set(signal_keys)) != len(signal_keys):
            msg = "duplicate business_signal key in AgentSpec"
            raise ValueError(msg)
        stars = [s.key for s in self.business_signals if s.north_star]
        if len(stars) > 1:
            # §6.1 — one north-star chip per agent card, never a heterogeneous sum.
            msg = f"at most one north_star business_signal per agent, got {stars}"
            raise ValueError(msg)
        return self


def parse_observability(raw: Mapping[str, object]) -> AgentObservabilitySpec:
    """Validate and build the observability block, raising ``ValueError`` on any issue.

    Wraps pydantic's :class:`ValidationError` in :class:`ValueError` so the registry
    loader keeps one uniform failure type (its enum-coercion errors already raise
    ``ValueError``), and a malformed manifest fails the load fast.
    """
    try:
        return AgentObservabilitySpec.model_validate(dict(raw))
    except ValidationError as exc:
        msg = f"invalid observability block: {exc}"
        raise ValueError(msg) from exc


class InvocationSpec(_Spec):
    """The AgentSpec ``invocation`` block — the declared cockpit→agent seam (ADR 0019 §1).

    The binding is *data*, never an import (the 0017 boundary ratchet stands): a declared
    consumer forwards a turn over the named transport, it does not reach into the runtime's
    module graph. The http-only fields are unrepresentable on the other bindings — a
    mis-declaration (an endpoint on a ``none`` agent, an ``http`` agent with no endpoint) is a
    load error, not a silently-ignored field, the same "make the illegal state
    unrepresentable" rule as the rest of the manifest.
    """

    binding: InvocationBinding = InvocationBinding.NONE
    endpoint: str | None = None  # http only — the agent EXPOSES; the cockpit consumes it
    timeout_ms: int | None = None  # http only
    auth: InvocationAuth | None = None  # http only; operator-assertion, no anonymous invocation
    # ADR 0019 §I4 — the scheduled-canary cadence. When set, a background canary drives one
    # synthetic turn through this binding every ``canary_cadence_s`` seconds (idle unless the
    # scheduler is enabled). A canary can only run through a real seam, so a cadence is
    # unrepresentable without an ``in_process_chat`` binding (the http canary is I3, not here).
    canary_cadence_s: int | None = None

    @model_validator(mode="after")
    def _binding_shape(self) -> InvocationSpec:
        http_only = {"endpoint": self.endpoint, "timeout_ms": self.timeout_ms, "auth": self.auth}
        if self.binding is InvocationBinding.HTTP:
            if not self.endpoint:
                msg = "invocation binding 'http' requires an endpoint (the turn contract URL)"
                raise ValueError(msg)
            if self.auth is None:
                # No anonymous invocation, ever (ADR 0019 §4): an http binding must name the
                # operator-assertion posture explicitly, never inherit a default.
                msg = "invocation binding 'http' requires auth (operator-assertion)"
                raise ValueError(msg)
            if self.timeout_ms is not None and self.timeout_ms <= 0:
                msg = f"invocation timeout_ms must be positive, got {self.timeout_ms}"
                raise ValueError(msg)
        else:
            present = sorted(key for key, value in http_only.items() if value is not None)
            if present:
                msg = (
                    f"invocation binding {self.binding.value!r} must not set http-only "
                    f"fields {present}"
                )
                raise ValueError(msg)
        if self.canary_cadence_s is not None:
            if self.binding is not InvocationBinding.IN_PROCESS_CHAT:
                # The canary scheduler drives the in_process_chat seam only (I4). A cadence on
                # ``none`` (nothing to drive) or ``http`` (the I3 invoker does not exist) is a
                # declaration the runtime cannot honour — reject it at load, never silently.
                msg = (
                    "invocation canary_cadence_s requires binding 'in_process_chat', "
                    f"got {self.binding.value!r}"
                )
                raise ValueError(msg)
            if self.canary_cadence_s <= 0:
                msg = f"invocation canary_cadence_s must be positive, got {self.canary_cadence_s}"
                raise ValueError(msg)
        return self


def parse_invocation(raw: Mapping[str, object]) -> InvocationSpec:
    """Validate and build the invocation block, raising ``ValueError`` on any issue.

    Same uniform-failure discipline as :func:`parse_observability`: pydantic's
    :class:`ValidationError` is wrapped so the registry loader has one failure type and a
    malformed block fails the load fast (a manifest is an API, not config).
    """
    try:
        return InvocationSpec.model_validate(dict(raw))
    except ValidationError as exc:
        msg = f"invalid invocation block: {exc}"
        raise ValueError(msg) from exc


def validate_quality_seam(
    observability: AgentObservabilitySpec | None, invocation: InvocationSpec
) -> None:
    """Reject a declared quality regime the runtime cannot honour (ADR 0026).

    Cross-block integrity the per-block validators cannot see: the online LLM judge is
    wired on the in-process ``/chat`` seam only, so an ``llm_judged`` declaration on any
    other invocation binding is a promise no line of code keeps. The registry loader calls
    this once both blocks are parsed — a contradictory manifest is a load error, never a
    surface quietly rendering a judge that will never come.

    Args:
        observability: The parsed observability block, or ``None`` for an un-manifested
            agent (nothing declared, nothing to contradict).
        invocation: The parsed invocation block (always present; honest default ``none``).

    Raises:
        ValueError: If the declared regime names a judge the declared seam cannot carry.
    """
    if observability is None:
        return
    if (
        observability.quality_regime is QualityRegime.LLM_JUDGED
        and invocation.binding is not InvocationBinding.IN_PROCESS_CHAT
    ):
        msg = (
            "quality_regime 'llm_judged' requires invocation binding 'in_process_chat' "
            f"(the online judge is wired on the /chat seam), got {invocation.binding.value!r}"
        )
        raise ValueError(msg)

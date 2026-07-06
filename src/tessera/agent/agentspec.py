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
    "PolicyMetadata",
    "PolicySeverity",
    "SignalEngagement",
    "WorkflowBinding",
    "parse_observability",
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

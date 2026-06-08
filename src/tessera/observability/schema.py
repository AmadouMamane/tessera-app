"""Versioned telemetry contract for Tessera's assurance layer."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ALLOWED_ATTRIBUTES",
    "FORBIDDEN_ATTRIBUTES",
    "LOW_CARDINALITY_METRIC_LABELS",
    "TelemetryEvent",
    "TelemetrySpan",
]


class TelemetryEvent(StrEnum):
    """Canonical event names emitted by the assurance layer."""

    TURN_STARTED = "TurnStarted"
    INTENT_DETECTED = "IntentDetected"
    TARGET_RESOLVED = "TargetResolved"
    POLICY_EVALUATED = "PolicyEvaluated"
    PROOF_ISSUED = "ProofIssued"
    TOOL_EXECUTION_STARTED = "ToolExecutionStarted"
    TOOL_EXECUTION_ALLOWED = "ToolExecutionAllowed"
    TOOL_EXECUTION_BLOCKED = "ToolExecutionBlocked"
    AUDIT_EMITTED = "AuditEmitted"
    EVIDENCE_COMMITTED = "EvidenceCommitted"
    TURN_COMPLETED = "TurnCompleted"


class TelemetrySpan(StrEnum):
    """Canonical span names for agent and safety operations."""

    TURN = "tessera.turn"
    ROUTER = "tessera.langgraph.router"
    PLANNER = "tessera.langgraph.planner"
    PRODUCT_LOOKUP = "tessera.langgraph.product_lookup"
    REGULATION_LOOKUP = "tessera.langgraph.regulation_lookup"
    ACCOUNT_LOOKUP = "tessera.langgraph.account_lookup"
    SIMULATOR = "tessera.langgraph.simulator"
    REVIEWER = "tessera.langgraph.reviewer"
    REPORTER = "tessera.langgraph.reporter"
    GUARD_DECISION = "tessera.guard.decision"
    RETRIEVAL_QUERY = "tessera.retrieval.query"
    LLM_CALL = "tessera.llm.call"
    MEMORY_OPERATION = "tessera.memory.operation"
    ESCALATION = "tessera.escalation"


ALLOWED_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "deployment.target",
        "observability.profile",
        "assurance.level",
        "request_id",
        "trace_id",
        "conversation_id_hash",
        "turn_id",
        "language",
        "model",
        "node",
        "outcome",
        "guard_verdict",
        "rule_id",
        "policy_hash",
        "prompt_hash",
        "corpus_hash",
        "citation_count",
        "retrieval_hit_count",
        "estimated_cost_eur",
        "proof_quality",
        "proof_consensus",
        "prompt_family",
        "prompt_version",
        "dataset_id",
        "experiment_id",
        "experiment_variant",
        "promotion_status",
        "llmops_view",
        "action_state",
        "target",
        "backend",
        "direction",
        "evidence_id",
        "langfuse.user.id",
        "langfuse.session.id",
        "langfuse.trace.name",
        "langfuse.trace.tags",
        "langfuse.version",
        "langfuse.environment",
        "langfuse.trace.metadata.observability_profile",
        "langfuse.trace.metadata.assurance_level",
        "langfuse.trace.metadata.langfuse_project",
        "langfuse.observation.type",
        "langfuse.observation.model.name",
        "langfuse.observation.usage_details",
        "gen_ai.system",
        "gen_ai.request.model",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
    }
)


FORBIDDEN_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "raw_prompt",
        "raw_completion",
        "iban",
        "pan",
        "email",
        "phone",
        "access_token",
        "secret",
        "full_name",
        "raw_account_id",
        "raw_card_id",
        "metric_label.conversation_id",
        "metric_label.turn_id",
    }
)


LOW_CARDINALITY_METRIC_LABELS: frozenset[str] = frozenset(
    {
        "language",
        "outcome",
        "node",
        "target",
        "decision",
        "profile",
        "assurance_level",
        "backend",
        "direction",
        "operation",
        "reason",
    }
)

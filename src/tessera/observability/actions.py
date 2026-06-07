"""Proof-carrying sensitive action primitives for the assurance layer."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from tessera.observability.evidence import canonical_hash
from tessera.settings import get_settings

__all__ = [
    "DecisionProof",
    "ProofValidation",
    "SensitiveActionPolicy",
    "active_policy_hash",
    "issue_decision_proof",
    "requires_decision_proof",
    "sensitive_action_policy",
    "validate_decision_proof",
]

_Verdict = Literal["allowed", "denied"]
_REPLAYED_DECISIONS: set[str] = set()


@dataclass(frozen=True, slots=True)
class SensitiveActionPolicy:
    """Declared assurance controls for a sensitive action."""

    tool_name: str
    proof_required: bool
    audit_required: bool
    evidence_level: str
    actor_scope: str
    target_scope: str
    replay_protection: bool


@dataclass(frozen=True, slots=True)
class DecisionProof:
    """Short-lived policy-bound proof attached to a sensitive tool call."""

    decision_id: str
    tool: str
    argument_hash: str
    context_hash: str
    policy_hash: str
    rule_id: str
    verdict: _Verdict
    reason_code: str
    issued_at: str
    expires_at: str
    evidence_level: str

    def model_dump(self) -> dict[str, str]:
        """Return a JSON-serializable representation."""
        return {
            "decision_id": self.decision_id,
            "tool": self.tool,
            "argument_hash": self.argument_hash,
            "context_hash": self.context_hash,
            "policy_hash": self.policy_hash,
            "rule_id": self.rule_id,
            "verdict": self.verdict,
            "reason_code": self.reason_code,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "evidence_level": self.evidence_level,
        }

    @property
    def proof_hash(self) -> str:
        """Stable hash of the proof payload."""
        return canonical_hash(self.model_dump())


@dataclass(frozen=True, slots=True)
class ProofValidation:
    """Validation result for a proof-carrying tool call."""

    valid: bool
    reason_code: str


_REGISTRY: dict[str, SensitiveActionPolicy] = {
    "card_block": SensitiveActionPolicy(
        tool_name="card_block",
        proof_required=True,
        audit_required=True,
        evidence_level="L3",
        actor_scope="authenticated_customer",
        target_scope="own_card_only",
        replay_protection=True,
    ),
    "account_balance": SensitiveActionPolicy(
        tool_name="account_balance",
        proof_required=True,
        audit_required=True,
        evidence_level="L3",
        actor_scope="authenticated_customer",
        target_scope="own_account_only",
        replay_protection=True,
    ),
    "loan_simulate": SensitiveActionPolicy(
        tool_name="loan_simulate",
        proof_required=False,
        audit_required=True,
        evidence_level="L2",
        actor_scope="authenticated_customer",
        target_scope="simulation_only",
        replay_protection=False,
    ),
    "ticket_escalate": SensitiveActionPolicy(
        tool_name="ticket_escalate",
        proof_required=False,
        audit_required=True,
        evidence_level="L2",
        actor_scope="authenticated_customer",
        target_scope="support_ticket",
        replay_protection=False,
    ),
}


def sensitive_action_policy(tool_name: str) -> SensitiveActionPolicy:
    """Return the declared sensitive-action policy for ``tool_name``."""
    return _REGISTRY.get(
        tool_name,
        SensitiveActionPolicy(
            tool_name=tool_name,
            proof_required=False,
            audit_required=True,
            evidence_level="L1",
            actor_scope="unknown",
            target_scope="unknown",
            replay_protection=False,
        ),
    )


def requires_decision_proof(tool_name: str) -> bool:
    """Return True when the action requires a proof before execution."""
    return sensitive_action_policy(tool_name).proof_required


def active_policy_hash() -> str:
    """Hash the active guard policy file for proof binding."""
    policy_path = get_settings().guard.policy_path
    try:
        return canonical_hash(policy_path.read_text(encoding="utf-8"))
    except OSError:
        return canonical_hash(str(policy_path))


def issue_decision_proof(
    *,
    tool_name: str,
    arguments: dict[str, object],
    context: dict[str, object],
    policy_hash: str,
    rule_id: str,
    verdict: _Verdict,
    reason_code: str,
    ttl_seconds: int = 30,
) -> DecisionProof:
    """Issue a short-lived proof for a sensitive action decision."""
    now = datetime.now(UTC)
    action_policy = sensitive_action_policy(tool_name)
    return DecisionProof(
        decision_id=f"dec_{uuid.uuid4().hex}",
        tool=tool_name,
        argument_hash=canonical_hash(arguments),
        context_hash=canonical_hash(context),
        policy_hash=policy_hash,
        rule_id=rule_id,
        verdict=verdict,
        reason_code=reason_code,
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
        evidence_level=action_policy.evidence_level,
    )


def validate_decision_proof(
    proof: DecisionProof,
    *,
    tool_name: str,
    arguments: dict[str, object],
    context: dict[str, object],
    policy_hash: str,
    now: datetime | None = None,
) -> ProofValidation:
    """Validate a proof against the actual sensitive tool invocation."""
    current = now or datetime.now(UTC)
    expires_at = datetime.fromisoformat(proof.expires_at)
    checks = (
        (proof.verdict == "allowed", "proof_verdict_not_allowed"),
        (proof.tool == tool_name, "tool_mismatch"),
        (proof.argument_hash == canonical_hash(arguments), "argument_hash_mismatch"),
        (proof.context_hash == canonical_hash(context), "context_hash_mismatch"),
        (proof.policy_hash == policy_hash, "policy_hash_mismatch"),
        (current <= expires_at, "proof_expired"),
    )
    for valid, reason_code in checks:
        if not valid:
            return ProofValidation(valid=False, reason_code=reason_code)
    if sensitive_action_policy(tool_name).replay_protection:
        if proof.decision_id in _REPLAYED_DECISIONS:
            return ProofValidation(valid=False, reason_code="proof_replayed")
        _REPLAYED_DECISIONS.add(proof.decision_id)
    return ProofValidation(valid=True, reason_code="proof_valid")

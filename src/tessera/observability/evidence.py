"""Redacted evidence bundle primitives for sensitive agent decisions."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tessera.observability.instrumentation import current_trace_id
from tessera.observability.privacy import hash_identifier, sanitize_attributes
from tessera.observability.profiles import resolve_profile
from tessera.settings import get_settings

__all__ = [
    "EvidenceBundle",
    "build_state_evidence_bundle",
    "build_turn_evidence_bundle",
    "canonical_hash",
    "list_recent_evidence_bundles",
    "persist_evidence_bundle",
]

_SCHEMA = "tessera.evidence_bundle.v1"


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Portable redacted evidence object for a turn or action."""

    evidence_id: str
    schema: str
    created_at: str
    turn_id: str
    conversation_id_hash: str
    profile: str
    assurance_level: str
    trace_id: str | None
    prompt_hash: str
    policy_hash: str | None
    corpus_hash: str | None
    model: str | None
    language: str | None
    attributes: dict[str, Any] = field(default_factory=dict)
    decision_rationale: dict[str, Any] = field(default_factory=dict)
    authorization_chain: list[dict[str, Any]] = field(default_factory=list)
    rejected_paths: list[str] = field(default_factory=list)
    guard_decisions: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieval_evidence: dict[str, Any] = field(default_factory=dict)
    citation_evidence: list[dict[str, Any]] = field(default_factory=list)
    audit_evidence: dict[str, Any] = field(default_factory=dict)
    evidence_gaps: list[str] = field(default_factory=list)
    proof_quality: str = "partial"
    proof_consensus: str = "0/0"
    privacy_status: str = "redacted"
    signature: str | None = None

    def model_dump(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "evidence_id": self.evidence_id,
            "schema": self.schema,
            "created_at": self.created_at,
            "turn_id": self.turn_id,
            "conversation_id_hash": self.conversation_id_hash,
            "profile": self.profile,
            "assurance_level": self.assurance_level,
            "trace_id": self.trace_id,
            "prompt_hash": self.prompt_hash,
            "policy_hash": self.policy_hash,
            "corpus_hash": self.corpus_hash,
            "model": self.model,
            "language": self.language,
            "attributes": self.attributes,
            "decision_rationale": self.decision_rationale,
            "authorization_chain": self.authorization_chain,
            "rejected_paths": self.rejected_paths,
            "guard_decisions": self.guard_decisions,
            "tool_calls": self.tool_calls,
            "retrieval_evidence": self.retrieval_evidence,
            "citation_evidence": self.citation_evidence,
            "audit_evidence": self.audit_evidence,
            "evidence_gaps": self.evidence_gaps,
            "proof_quality": self.proof_quality,
            "proof_consensus": self.proof_consensus,
            "privacy_status": self.privacy_status,
            "signature": self.signature,
        }


def _prompt_hash() -> str:
    settings = get_settings().observability
    source = f"{settings.prompt_family}:{settings.prompt_version}"
    return hash_identifier(source)


def _sign(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    # V1 uses a deterministic local development key; regulated deployments will
    # swap this for KMS/HSM-backed signing without changing the bundle schema.
    digest = hmac.new(b"tessera-evidence-v1", body, hashlib.sha256).hexdigest()
    return "hmac-sha256:" + digest


def canonical_hash(value: object) -> str:
    """Return a stable SHA-256 hash for JSON-compatible evidence fragments."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _safe_decision(record: object) -> dict[str, Any]:
    """Convert a guard decision record into a redacted evidence fragment."""
    target = getattr(record, "target", "unknown")
    decision = getattr(record, "decision", "unknown")
    policy_rule = getattr(record, "policy_rule", "unknown")
    rationale = getattr(record, "rationale", "")
    return {
        "target": str(target),
        "decision": str(decision),
        "rule_id": str(policy_rule),
        "rationale_hash": canonical_hash(rationale),
        "redactions": list(getattr(record, "redactions", ()) or ()),
    }


def _safe_tool_call(call: object) -> dict[str, Any]:
    """Convert a tool call record into a redacted evidence fragment."""
    arguments = getattr(call, "arguments", {}) or {}
    return {
        "tool_name": str(getattr(call, "tool_name", "unknown")),
        "argument_hash": canonical_hash(arguments),
        "result_type": type(getattr(call, "result", None)).__name__,
        "succeeded": bool(getattr(call, "succeeded", False)),
        "error": getattr(call, "error", None),
        "duration_ms": float(getattr(call, "duration_ms", 0.0) or 0.0),
        "decision_proof_id": getattr(call, "decision_proof_id", None),
        "decision_proof_hash": getattr(call, "decision_proof_hash", None),
    }


def _safe_citation(citation: object) -> dict[str, Any]:
    """Convert a citation into a redacted evidence fragment."""
    return {
        "source": str(getattr(citation, "source", "unknown")),
        "locator": str(getattr(citation, "locator", "unknown")),
        "language": str(getattr(getattr(citation, "language", None), "value", "unknown")),
        "excerpt_hash": canonical_hash(getattr(citation, "excerpt", "")),
    }


def _proof_consensus(*, trace_id: str | None, guard_count: int, tool_count: int) -> tuple[str, str]:
    """Return ``(proof_quality, consensus)`` for the available evidence sources."""
    denominator = 3
    numerator = 1  # runtime state is the source that asked us to build the bundle
    if trace_id:
        numerator += 1
    if guard_count or tool_count:
        numerator += 1
    quality = "complete" if numerator == denominator else "partial"
    return quality, f"{numerator}/{denominator}"


def build_turn_evidence_bundle(
    *,
    conversation_id: uuid.UUID | str,
    turn_id: uuid.UUID | str,
    trace_id: str | None = None,
    model: str | None = None,
    language: str | None = None,
    attributes: dict[str, Any] | None = None,
    decision_rationale: dict[str, Any] | None = None,
    authorization_chain: list[dict[str, Any]] | None = None,
    rejected_paths: list[str] | None = None,
    guard_decisions: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    retrieval_evidence: dict[str, Any] | None = None,
    citation_evidence: list[dict[str, Any]] | None = None,
    audit_evidence: dict[str, Any] | None = None,
    evidence_gaps: list[str] | None = None,
) -> EvidenceBundle:
    """Build a redacted evidence bundle for a completed turn."""
    profile = resolve_profile()
    sanitized = sanitize_attributes(attributes or {})
    evidence_id = f"ev_{uuid.uuid4().hex}"
    created_at = datetime.now(UTC).isoformat()
    prompt_hash = _prompt_hash()
    proof_quality, proof_consensus = _proof_consensus(
        trace_id=trace_id,
        guard_count=len(guard_decisions or []),
        tool_count=len(tool_calls or []),
    )
    policy_hash = sanitized.get("policy_hash")
    corpus_hash = sanitized.get("corpus_hash")
    payload: dict[str, Any] = {
        "evidence_id": evidence_id,
        "schema": _SCHEMA,
        "created_at": created_at,
        "turn_id": str(turn_id),
        "conversation_id_hash": hash_identifier(conversation_id),
        "profile": profile.name.value,
        "assurance_level": profile.assurance_level.value,
        "trace_id": trace_id,
        "prompt_hash": prompt_hash,
        "policy_hash": policy_hash,
        "corpus_hash": corpus_hash,
        "model": model,
        "language": language,
        "attributes": sanitized,
        "decision_rationale": decision_rationale or {},
        "authorization_chain": authorization_chain or [],
        "rejected_paths": rejected_paths or [],
        "guard_decisions": guard_decisions or [],
        "tool_calls": tool_calls or [],
        "retrieval_evidence": retrieval_evidence or {},
        "citation_evidence": citation_evidence or [],
        "audit_evidence": audit_evidence or {},
        "evidence_gaps": evidence_gaps or [],
        "proof_quality": proof_quality,
        "proof_consensus": proof_consensus,
        "privacy_status": "redacted",
    }
    signature = None
    if profile.evidence_signing_enabled:
        signature = _sign(payload)
    return EvidenceBundle(
        evidence_id=evidence_id,
        schema=_SCHEMA,
        created_at=created_at,
        turn_id=str(turn_id),
        conversation_id_hash=hash_identifier(conversation_id),
        profile=profile.name.value,
        assurance_level=profile.assurance_level.value,
        trace_id=trace_id,
        prompt_hash=prompt_hash,
        policy_hash=str(policy_hash) if policy_hash is not None else None,
        corpus_hash=str(corpus_hash) if corpus_hash is not None else None,
        model=model,
        language=language,
        attributes=sanitized,
        decision_rationale=decision_rationale or {},
        authorization_chain=authorization_chain or [],
        rejected_paths=rejected_paths or [],
        guard_decisions=guard_decisions or [],
        tool_calls=tool_calls or [],
        retrieval_evidence=retrieval_evidence or {},
        citation_evidence=citation_evidence or [],
        audit_evidence=audit_evidence or {},
        evidence_gaps=evidence_gaps or [],
        proof_quality=proof_quality,
        proof_consensus=proof_consensus,
        privacy_status="redacted",
        signature=signature,
    )


def build_state_evidence_bundle(
    state: Mapping[str, Any],
    *,
    final_response: str,
    trace_id: str | None = None,
) -> EvidenceBundle:
    """Build a redacted evidence bundle from a completed agent state."""
    resolved_trace_id = trace_id or current_trace_id()
    guard_records = list(state.get("guard_decisions", []) or [])
    tool_records = list(state.get("tool_calls", []) or [])
    documents = list(state.get("retrieved_documents", []) or [])
    citations = list(state.get("citations", []) or [])
    errors = [str(item) for item in state.get("errors", []) or []]
    rejected_paths = [
        *_safe_rejected_paths(guard_records),
        *[error for error in errors if "refused" in error or "failed" in error],
    ]
    evidence_gaps: list[str] = []
    if resolved_trace_id is None:
        evidence_gaps.append("missing_trace")
    if not guard_records:
        evidence_gaps.append("missing_guard_decision")
    if state.get("needs_escalation") and not any(
        getattr(call, "tool_name", "") == "ticket_escalate" for call in tool_records
    ):
        evidence_gaps.append("missing_escalation_tool_call")
    if documents and not citations:
        evidence_gaps.append("retrieval_without_citation")
    language = state.get("language")
    language_value = getattr(language, "value", language)
    return build_turn_evidence_bundle(
        conversation_id=state["conversation_id"],
        turn_id=state["turn_id"],
        trace_id=resolved_trace_id,
        model=str(state.get("model")) if state.get("model") is not None else None,
        language=str(language_value) if language_value is not None else None,
        attributes={
            "language": str(language_value) if language_value is not None else "",
            "model": str(state.get("model", "")),
            "citation_count": len(citations),
            "retrieval_hit_count": len(documents),
        },
        decision_rationale={
            "needs_escalation": bool(state.get("needs_escalation", False)),
            "confidence": state.get("confidence"),
            "plan_rationale": state.get("plan_rationale"),
            "final_response_hash": canonical_hash(final_response),
        },
        rejected_paths=rejected_paths,
        guard_decisions=[_safe_decision(record) for record in guard_records],
        tool_calls=[_safe_tool_call(call) for call in tool_records],
        retrieval_evidence={
            "document_count": len(documents),
            "sources": sorted({str(getattr(doc, "source", "unknown")) for doc in documents}),
            "chunk_hashes": [canonical_hash(getattr(doc, "chunk_id", "")) for doc in documents],
        },
        citation_evidence=[_safe_citation(citation) for citation in citations],
        audit_evidence={
            "guard_decision_count": len(guard_records),
            "tool_call_count": len(tool_records),
            "audit_sink_expected": get_settings().guard.audit_sink,
        },
        evidence_gaps=evidence_gaps,
    )


def _safe_rejected_paths(guard_records: list[object]) -> list[str]:
    """Return redacted rejected-path labels derived from denied guard records."""
    rejected: list[str] = []
    for record in guard_records:
        if getattr(record, "decision", "") == "deny":
            target = str(getattr(record, "target", "unknown"))
            rule = str(getattr(record, "policy_rule", "unknown"))
            rejected.append(f"{target}:{rule}")
    return rejected


def persist_evidence_bundle(bundle: EvidenceBundle, *, base_dir: Path | None = None) -> Path:
    """Persist ``bundle`` as an immutable redacted JSON file and return its path."""
    settings_dir = get_settings().observability.evidence_dir
    root = base_dir or settings_dir
    created = datetime.fromisoformat(bundle.created_at)
    target_dir = root / created.strftime("%Y-%m-%d")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{bundle.evidence_id}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(bundle.model_dump(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(target)
    return target


def list_recent_evidence_bundles(
    *,
    limit: int = 10,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """List recent persisted evidence bundle summaries."""
    root = base_dir or get_settings().observability.evidence_dir
    if not root.exists():
        return []
    files = sorted(root.glob("*/*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    summaries: list[dict[str, Any]] = []
    for path in files[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summaries.append(
            {
                "evidence_id": data.get("evidence_id"),
                "created_at": data.get("created_at"),
                "turn_id": data.get("turn_id"),
                "profile": data.get("profile"),
                "assurance_level": data.get("assurance_level"),
                "proof_quality": data.get("proof_quality"),
                "proof_consensus": data.get("proof_consensus"),
                "privacy_status": data.get("privacy_status"),
                "evidence_gaps": data.get("evidence_gaps", []),
            }
        )
    return summaries

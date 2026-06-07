"""Observability assurance status and evidence endpoints."""

from __future__ import annotations

import uuid  # noqa: TCH003  Pydantic resolves UUID annotations at runtime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from tessera.observability.digital_twin import run_assurance_twin
from tessera.observability.evidence import (
    build_turn_evidence_bundle,
    list_recent_evidence_bundles,
    persist_evidence_bundle,
)
from tessera.observability.langfuse import langfuse_status
from tessera.observability.metrics import OBSERVABILITY_COMPLETENESS, PROOF_CONSENSUS
from tessera.observability.profiles import resolve_profile
from tessera.observability.schema import (
    ALLOWED_ATTRIBUTES,
    FORBIDDEN_ATTRIBUTES,
    LOW_CARDINALITY_METRIC_LABELS,
)
from tessera.observability.verifier import shadow_verify_recent
from tessera.settings import get_settings

router = APIRouter(prefix="/observability", tags=["observability"])


class ExporterStatus(BaseModel):
    """Resolved exporter posture for the active profile."""

    collector_required: bool
    collector_configured: bool
    langfuse_enabled: bool
    langfuse_configured: bool
    primary_backend: str
    evidence_enabled: bool
    evidence_signing_enabled: bool
    raw_prompts_export: bool
    pii_export: bool


class LLMOpsStatus(BaseModel):
    """Optional Langfuse cockpit posture."""

    enabled: bool
    configured: bool
    status: str
    host: str | None
    role: str


class AssuranceStatus(BaseModel):
    """Computed conformance status for the active profile."""

    target_level: str
    current_level: str
    completeness: float
    proof_consensus: float
    proof_slo_status: str
    missing_controls: list[str]


class EvidenceSummary(BaseModel):
    """Recent persisted evidence bundle summary."""

    evidence_id: str | None
    created_at: str | None
    turn_id: str | None
    profile: str | None
    assurance_level: str | None
    proof_quality: str | None
    proof_consensus: str | None
    privacy_status: str | None
    evidence_gaps: list[str]


class VerificationFindingModel(BaseModel):
    """One shadow-verifier finding."""

    code: str
    severity: str
    message: str


class VerificationReportModel(BaseModel):
    """One shadow-verifier report."""

    evidence_id: str | None
    status: str
    findings: list[VerificationFindingModel]


class ObservabilityStatus(BaseModel):
    """Public operator status for the assurance layer."""

    profile: str
    assurance_level: str
    status: str
    exporters: ExporterStatus
    llmops: LLMOpsStatus
    assurance: AssuranceStatus
    recent_evidence: list[EvidenceSummary]
    allowed_attribute_count: int
    forbidden_attribute_count: int
    low_cardinality_metric_labels: list[str]
    prompt_family: str
    prompt_version: str
    dataset_id: str | None
    experiment_id: str | None
    experiment_variant: str | None
    warnings: list[str]


class ObservabilityConformance(BaseModel):
    """Recent conformance and twin matrix status."""

    reports: list[VerificationReportModel]
    twin_scenarios: list[dict[str, object]]


class EvidencePreviewRequest(BaseModel):
    """Minimal request to preview a redacted evidence bundle."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: uuid.UUID
    turn_id: uuid.UUID
    trace_id: str | None = Field(default=None, max_length=200)
    model: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=8)
    attributes: dict[str, Any] = Field(default_factory=dict, max_length=40)


def _warnings() -> list[str]:
    settings = get_settings()
    profile = resolve_profile(settings)
    obs = settings.observability
    warnings: list[str] = []
    if profile.collector_required and not obs.otel_endpoint and not obs.cloud_logging_project:
        warnings.append("collector_required_but_not_configured")
    if profile.langfuse_enabled and not obs.langfuse_host:
        warnings.append("langfuse_enabled_but_not_configured")
    if obs.raw_prompts_export:
        warnings.append("raw_prompt_export_enabled")
    if obs.pii_export:
        warnings.append("pii_export_enabled")
    if not obs.evidence_enabled:
        warnings.append("evidence_disabled")
    return warnings


def _assurance_status(warnings: list[str]) -> AssuranceStatus:
    """Compute a conservative assurance score from profile conformance checks."""
    settings = get_settings()
    profile = resolve_profile(settings)
    obs = settings.observability
    collector_configured = bool(obs.otel_endpoint or obs.cloud_logging_project)
    checks = {
        "privacy_gateway": not obs.raw_prompts_export and not obs.pii_export,
        "collector": collector_configured or not profile.collector_required,
        "evidence": profile.evidence_enabled,
        "langfuse_optional": (not profile.langfuse_enabled) or bool(obs.langfuse_host),
        "audit_sink": bool(settings.guard.audit_sink),
    }
    passed = sum(1 for ok in checks.values() if ok)
    completeness = passed / len(checks)
    missing = [name for name, ok in checks.items() if not ok]
    current_level = profile.assurance_level.value
    if warnings:
        current_level = (
            "L2" if profile.assurance_level.value in {"L3", "L4", "L5"} else current_level
        )
    proof_consensus = 1.0 if not missing else max(0.0, 1.0 - (len(missing) * 0.2))
    OBSERVABILITY_COMPLETENESS.labels(
        profile=profile.name.value,
        assurance_level=profile.assurance_level.value,
    ).set(completeness)
    PROOF_CONSENSUS.labels(
        profile=profile.name.value,
        assurance_level=profile.assurance_level.value,
    ).set(proof_consensus)
    return AssuranceStatus(
        target_level=profile.assurance_level.value,
        current_level=current_level,
        completeness=round(completeness, 3),
        proof_consensus=round(proof_consensus, 3),
        proof_slo_status="ok" if not missing else "degraded",
        missing_controls=missing,
    )


@router.get("/status", response_model=ObservabilityStatus)
async def status() -> ObservabilityStatus:
    """Return the active observability assurance posture."""
    settings = get_settings()
    profile = resolve_profile(settings)
    obs = settings.observability
    warnings = _warnings()
    collector_configured = bool(obs.otel_endpoint or obs.cloud_logging_project)
    llmops = langfuse_status()
    return ObservabilityStatus(
        profile=profile.name.value,
        assurance_level=profile.assurance_level.value,
        status="degraded" if warnings else "ok",
        exporters=ExporterStatus(
            collector_required=profile.collector_required,
            collector_configured=collector_configured,
            langfuse_enabled=profile.langfuse_enabled,
            langfuse_configured=bool(obs.langfuse_host),
            primary_backend=profile.primary_backend,
            evidence_enabled=profile.evidence_enabled,
            evidence_signing_enabled=profile.evidence_signing_enabled,
            raw_prompts_export=profile.raw_prompts_export,
            pii_export=profile.pii_export,
        ),
        llmops=LLMOpsStatus(
            enabled=llmops.enabled,
            configured=llmops.configured,
            status=llmops.status,
            host=llmops.host,
            role=llmops.role,
        ),
        assurance=_assurance_status(warnings),
        recent_evidence=[
            EvidenceSummary.model_validate(item) for item in list_recent_evidence_bundles(limit=5)
        ],
        allowed_attribute_count=len(ALLOWED_ATTRIBUTES),
        forbidden_attribute_count=len(FORBIDDEN_ATTRIBUTES),
        low_cardinality_metric_labels=sorted(LOW_CARDINALITY_METRIC_LABELS),
        prompt_family=obs.prompt_family,
        prompt_version=obs.prompt_version,
        dataset_id=obs.dataset_id,
        experiment_id=obs.experiment_id,
        experiment_variant=obs.experiment_variant,
        warnings=warnings,
    )


@router.post("/evidence/preview")
async def preview_evidence(payload: EvidencePreviewRequest) -> dict[str, Any]:
    """Build a redacted evidence bundle without persisting it."""
    bundle = build_turn_evidence_bundle(
        conversation_id=payload.conversation_id,
        turn_id=payload.turn_id,
        trace_id=payload.trace_id,
        model=payload.model,
        language=payload.language,
        attributes=payload.attributes,
    )
    return bundle.model_dump()


@router.post("/evidence/commit")
async def commit_evidence(payload: EvidencePreviewRequest) -> dict[str, Any]:
    """Build and persist a redacted evidence bundle for operator workflows."""
    bundle = build_turn_evidence_bundle(
        conversation_id=payload.conversation_id,
        turn_id=payload.turn_id,
        trace_id=payload.trace_id,
        model=payload.model,
        language=payload.language,
        attributes=payload.attributes,
    )
    path = persist_evidence_bundle(bundle)
    body = bundle.model_dump()
    body["persisted"] = True
    body["storage"] = {"kind": "local_redacted_json", "path": str(path)}
    return body


@router.get("/conformance", response_model=ObservabilityConformance)
async def conformance() -> ObservabilityConformance:
    """Return shadow verification reports and the current assurance twin matrix."""
    return ObservabilityConformance(
        reports=[
            VerificationReportModel.model_validate(report.model_dump())
            for report in shadow_verify_recent(limit=10)
        ],
        twin_scenarios=[scenario.model_dump() for scenario in run_assurance_twin()],
    )

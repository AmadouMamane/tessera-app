"""Deployment-aware observability assurance profile resolution."""

from __future__ import annotations

from dataclasses import dataclass

from tessera.settings import (
    AssuranceLevel,
    DeploymentMode,
    ObservabilityProfile,
    Settings,
    get_settings,
)

__all__ = ["ResolvedObservabilityProfile", "resolve_profile"]


@dataclass(frozen=True, slots=True)
class ResolvedObservabilityProfile:
    """Materialized observability profile used by status and evidence code."""

    name: ObservabilityProfile
    assurance_level: AssuranceLevel
    collector_required: bool
    langfuse_enabled: bool
    raw_prompts_export: bool
    pii_export: bool
    evidence_enabled: bool
    evidence_signing_enabled: bool
    primary_backend: str


def _default_profile(settings: Settings) -> ObservabilityProfile:
    if settings.observability.profile is not None:
        return settings.observability.profile
    if settings.environment.value == "local":
        return ObservabilityProfile.LOCAL_DEV
    if settings.deployment_mode is DeploymentMode.ON_PREM:
        return ObservabilityProfile.ON_PREM_STANDARD
    if settings.is_production():
        return ObservabilityProfile.CLOUD_GCP_REGULATED
    return ObservabilityProfile.CLOUD_GCP_STANDARD


def _default_level(profile: ObservabilityProfile) -> AssuranceLevel:
    match profile:
        case ObservabilityProfile.LOCAL_DEV:
            return AssuranceLevel.L1_CORRELATED
        case ObservabilityProfile.DEMO_PREMIUM:
            return AssuranceLevel.L3_VERIFIABLE
        case ObservabilityProfile.CLOUD_GCP_STANDARD | ObservabilityProfile.ON_PREM_STANDARD:
            return AssuranceLevel.L3_VERIFIABLE
        case ObservabilityProfile.CLOUD_GCP_REGULATED:
            return AssuranceLevel.L4_REPLAYABLE
        case ObservabilityProfile.ON_PREM_AIRGAPPED:
            return AssuranceLevel.L5_CERTIFIABLE


def resolve_profile(settings: Settings | None = None) -> ResolvedObservabilityProfile:
    """Resolve the active observability profile with conservative defaults."""
    active = settings or get_settings()
    obs = active.observability
    profile = _default_profile(active)
    level = obs.assurance_level or _default_level(profile)
    collector_required = obs.collector_required
    if collector_required is None:
        collector_required = profile is not ObservabilityProfile.LOCAL_DEV
    signing = obs.evidence_signing_enabled
    if signing is None:
        signing = level in {
            AssuranceLevel.L3_VERIFIABLE,
            AssuranceLevel.L4_REPLAYABLE,
            AssuranceLevel.L5_CERTIFIABLE,
        }
    if profile in {
        ObservabilityProfile.CLOUD_GCP_STANDARD,
        ObservabilityProfile.CLOUD_GCP_REGULATED,
    }:
        backend = "google_cloud_observability"
    elif profile is ObservabilityProfile.LOCAL_DEV:
        backend = "local_console"
    else:
        backend = "sovereign_otel_stack"
    return ResolvedObservabilityProfile(
        name=profile,
        assurance_level=level,
        collector_required=collector_required,
        langfuse_enabled=obs.langfuse_enabled,
        raw_prompts_export=obs.raw_prompts_export,
        pii_export=obs.pii_export,
        evidence_enabled=obs.evidence_enabled,
        evidence_signing_enabled=signing,
        primary_backend=backend,
    )

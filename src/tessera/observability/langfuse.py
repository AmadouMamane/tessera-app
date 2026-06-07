"""Optional Langfuse bridge metadata for the non-canonical LLMOps cockpit."""

from __future__ import annotations

from dataclasses import dataclass

from tessera.observability.profiles import resolve_profile
from tessera.settings import get_settings

__all__ = ["LangfuseBridgeStatus", "langfuse_metadata", "langfuse_status"]


@dataclass(frozen=True, slots=True)
class LangfuseBridgeStatus:
    """Health posture for the optional Langfuse cockpit."""

    enabled: bool
    configured: bool
    status: str
    host: str | None
    role: str


def langfuse_status() -> LangfuseBridgeStatus:
    """Return the optional Langfuse bridge status without probing the network."""
    settings = get_settings().observability
    profile = resolve_profile()
    enabled = profile.langfuse_enabled
    configured = bool(settings.langfuse_host)
    if not enabled:
        status = "disabled"
    elif configured:
        status = "configured"
    else:
        status = "degraded"
    return LangfuseBridgeStatus(
        enabled=enabled,
        configured=configured,
        status=status,
        host=settings.langfuse_host,
        role="optional_llmops_cockpit",
    )


def langfuse_metadata() -> dict[str, str | None]:
    """Return prompt, dataset, and experiment metadata mirrored to Langfuse."""
    settings = get_settings().observability
    return {
        "prompt_family": settings.prompt_family,
        "prompt_version": settings.prompt_version,
        "dataset_id": settings.dataset_id,
        "experiment_id": settings.experiment_id,
        "experiment_variant": settings.experiment_variant,
    }

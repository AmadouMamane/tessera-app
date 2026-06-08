"""Optional Langfuse bridge metadata for the non-canonical LLMOps cockpit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tessera.observability.profiles import resolve_profile
from tessera.settings import get_settings

__all__ = [
    "LangfuseBridgeStatus",
    "generation_span_attributes",
    "langfuse_metadata",
    "langfuse_status",
]


@dataclass(frozen=True, slots=True)
class LangfuseBridgeStatus:
    """Health posture for the optional Langfuse cockpit."""

    enabled: bool
    configured: bool
    credentials_configured: bool
    status: str
    host: str | None
    project: str
    ingestion_mode: str
    role: str


def _secret_is_configured(value: object) -> bool:
    get_secret_value = getattr(value, "get_secret_value", None)
    if callable(get_secret_value):
        return bool(get_secret_value())
    return bool(value)


def langfuse_status() -> LangfuseBridgeStatus:
    """Return the optional Langfuse bridge status without probing the network."""
    settings = get_settings().observability
    profile = resolve_profile()
    enabled = profile.langfuse_enabled
    credentials_configured = _secret_is_configured(settings.langfuse_public_key) and (
        _secret_is_configured(settings.langfuse_secret_key)
    )
    configured = bool(settings.langfuse_host and credentials_configured)
    public_host = settings.langfuse_public_url or settings.langfuse_host
    if not enabled:
        status = "linked" if public_host else "disabled"
    elif configured:
        status = "configured"
    else:
        status = "degraded"
    return LangfuseBridgeStatus(
        enabled=enabled,
        configured=configured,
        credentials_configured=credentials_configured,
        status=status,
        host=public_host,
        project=settings.langfuse_project,
        ingestion_mode=settings.langfuse_ingestion_mode,
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


def generation_span_attributes(
    *,
    backend: str,
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> dict[str, Any]:
    """Return privacy-safe GenAI attributes mapped cleanly by Langfuse OTel."""
    attributes: dict[str, Any] = {
        "backend": backend,
        "model": model,
        "langfuse.observation.type": "generation",
        "langfuse.observation.model.name": model,
        "gen_ai.system": backend,
        "gen_ai.request.model": model,
    }
    usage: dict[str, int] = {}
    if input_tokens is not None:
        attributes["gen_ai.usage.input_tokens"] = input_tokens
        usage["input"] = input_tokens
    if output_tokens is not None:
        attributes["gen_ai.usage.output_tokens"] = output_tokens
        usage["output"] = output_tokens
    if usage:
        attributes["langfuse.observation.usage_details"] = json.dumps(
            usage,
            sort_keys=True,
            separators=(",", ":"),
        )
    return attributes

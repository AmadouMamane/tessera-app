"""Observability route for the live facts on `/comprendre`."""

from __future__ import annotations

import sys
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import ValidationError

from tessera.api.routes import audit as audit_routes
from tessera.api.routes.observability.schemas_comprendre import (
    ComprendrePayload,
    ComprendreUnavailable,
)
from tessera.observability import comprendre as comprendre_mod

router = APIRouter()


@router.get(
    "/observability/comprendre",
    response_model=ComprendrePayload | ComprendreUnavailable,
)
async def observability_comprendre() -> ComprendrePayload | ComprendreUnavailable:
    """Compose the six live facts paired with the four explanatory tiles.

    Audit freshness is obtained only by running the exact same ``audit_integrity`` function as
    the cockpit badge. The other three sources degrade independently inside the observability
    builder, so a silent fleet never erases a valid journal or release fact.
    """
    checked_at = datetime.now(UTC)
    verification: comprendre_mod.AuditVerification | None = None
    try:
        integrity = await audit_routes.audit_integrity()
        verification = comprendre_mod.AuditVerification(
            verified=integrity.verified,
            length=integrity.length,
            full_verified_at=integrity.full_verified_at,
            checked_at=checked_at,
        )
    except Exception as exc:
        sys.stderr.write(f"tessera.observability.comprendre.audit: failed: {exc}\n")
    try:
        data = await comprendre_mod.build_comprendre(verification, now=checked_at)
        return ComprendrePayload.model_validate({"available": True, **data})
    except (ValidationError, ValueError) as exc:
        sys.stderr.write(f"tessera.observability.comprendre: CONTRACT BREAK: {exc}\n")
        return ComprendreUnavailable(available=False)

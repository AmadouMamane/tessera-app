"""Observability routes — client surface."""

from __future__ import annotations

import sys

from fastapi import APIRouter

from tessera.observability import (
    client_space as client_space_mod,
)

router = APIRouter()


@router.get("/observability/client/documents")
def observability_client_documents(locale: str = "fr") -> dict[str, object]:
    """Customer documents, sourced from the real Crédit Aurore corpus (locale-aware)."""
    try:
        return {"available": True, **client_space_mod.compute_documents(locale)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.documents: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/client/requests")
def observability_client_requests(lang: str = "fr") -> dict[str, object]:
    """Customer support requests (escalation tickets)."""
    try:
        return {"available": True, **client_space_mod.compute_requests(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.requests: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/client/alerts")
def observability_client_alerts(lang: str = "fr") -> dict[str, object]:
    """Account alerts with the durable read-state applied."""
    try:
        return {"available": True, **client_space_mod.compute_alerts(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.alerts: failed: {exc}\n")
        return {"available": False}


@router.get("/observability/client/settings")
def observability_client_settings(lang: str = "fr") -> dict[str, object]:
    """Customer preferences (notifications, privacy/consent, security)."""
    try:
        return {"available": True, **client_space_mod.compute_settings(lang)}
    except Exception as exc:  # never break the page
        sys.stderr.write(f"tessera.observability.client_space.settings: failed: {exc}\n")
        return {"available": False}

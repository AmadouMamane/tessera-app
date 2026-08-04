"""Runtime telemetry spine (ADR 0015).

A first-class :class:`~tessera.observability.spine.scope.Scope`, a capability-declared
signal registry, and a batched, cached snapshot read model. Phase A wires the read
model over the *current* stores (``scores.jsonl`` / ``bundles.jsonl`` + the tamper-evident
ledger) behind an adapter seam; later phases swap the adapter to the live spine
(Prometheus / Langfuse) **without changing this interface**.

The point of the package is honesty made structural: a signal *declares* the dimensions
it supports (:mod:`capabilities`), the read layer *reports* what it honoured vs ignored,
and the UI derives org-wide / provenance disclosures from that contract — so the illegal state
"a filter is shown but silently ignored" is unrepresentable.
"""

from __future__ import annotations

from tessera.observability.spine.capabilities import (
    CAPABILITIES,
    SignalCapability,
    SignalProvenance,
    capability_for,
    snapshot_signal_ids,
)
from tessera.observability.spine.registry import (
    ScopeReport,
    SignalRegistry,
    SignalResult,
    SignalSpec,
    get_registry,
)
from tessera.observability.spine.scope import Dimension, Scope

__all__ = [
    "CAPABILITIES",
    "Dimension",
    "Scope",
    "ScopeReport",
    "SignalCapability",
    "SignalProvenance",
    "SignalRegistry",
    "SignalResult",
    "SignalSpec",
    "capability_for",
    "get_registry",
    "snapshot_signal_ids",
]

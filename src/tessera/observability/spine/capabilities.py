"""Per-signal capability declarations — the single source of honesty truth (ADR 0015).

Each signal declares which :class:`~tessera.observability.spine.scope.Dimension` s it can
be sliced by, whether it is a deterministic fixture (``synthetic``), and its migration
``source`` (``jsonl`` / ``spine`` / ``shadow``). The read layer intersects the request
``Scope`` with these dimensions and *reports* what it honoured, so the UI badges
"org-wide" / "synthetic" from data — never a hand-placed note.

A signal that **omits** ``AGENT`` is org-wide *by construction*: a fixed-corpus probe of
the shared policy (``refusal``, ``firewall``) has no per-agent substrate to slice, and a
crypto invariant (audit-chain ``integrity``) is a whole-fleet property whose per-agent
sub-chain would be a *weaker* guarantee. Omitting the dimension is the honest encoding —
the UI then shows "org-wide" automatically and truthfully.
"""

from __future__ import annotations

from dataclasses import dataclass

from tessera.observability.spine.scope import Dimension

__all__ = [
    "CAPABILITIES",
    "SOURCE_JSONL",
    "SOURCE_SHADOW",
    "SOURCE_SPINE",
    "SignalCapability",
    "capability_for",
    "snapshot_signal_ids",
]

AGENT = Dimension.AGENT
TIME = Dimension.TIME
LANGUAGE = Dimension.LANGUAGE
MODEL = Dimension.MODEL

# Migration source flag (ADR 0015 §Testing 3): a signal is flipped jsonl→spine per-signal,
# and can shadow-run both before flipping. Phase A: everything reads ``jsonl``.
SOURCE_JSONL = "jsonl"
SOURCE_SPINE = "spine"
SOURCE_SHADOW = "shadow"


@dataclass(frozen=True, slots=True)
class SignalCapability:
    """What a signal can be sliced by, and how honestly to present it."""

    id: str
    dimensions: frozenset[Dimension]
    synthetic: bool = False
    source: str = SOURCE_JSONL
    # Whether the batched snapshot hot path computes this signal (store-derived,
    # scope-varying). Org-wide fixed-corpus probes are declared here for their badges
    # but served by their own cached endpoints, so they stay off the hot path.
    in_snapshot: bool = False

    @property
    def org_wide(self) -> bool:
        """True when the signal cannot be sliced by agent (org-wide by construction)."""
        return Dimension.AGENT not in self.dimensions


def _cap(
    signal_id: str,
    dims: set[Dimension] | frozenset[Dimension] = frozenset(),
    *,
    synthetic: bool = False,
    source: str = SOURCE_JSONL,
    in_snapshot: bool = False,
) -> SignalCapability:
    return SignalCapability(
        id=signal_id,
        dimensions=frozenset(dims),
        synthetic=synthetic,
        source=source,
        in_snapshot=in_snapshot,
    )


# The full dimensioning of a store-derived turn signal: sliceable by agent, time, language and
# model, because the score rows / captured bundles carry all four (ADR 0015 §Migration F — the
# cube). Declaring the dimension is a field here, not a route sweep; the read narrows the request
# scope to exactly these, so an unsupported slice can never be silently applied.
_CUBE = {AGENT, TIME, LANGUAGE, MODEL}

# --- The declaration table (the honesty contract, mirrored by lib/signal-registry.ts) ---
_DECLARATIONS: tuple[SignalCapability, ...] = (
    # Store-derived, per-agent + as-of-T + language + model — the batched snapshot hot path.
    _cap("scores", _CUBE, in_snapshot=True),
    _cap("slo", _CUBE, in_snapshot=True),
    _cap("trend", _CUBE, in_snapshot=True),
    _cap("funnel", _CUBE, in_snapshot=True),
    _cap("toxicity", _CUBE, in_snapshot=True),
    _cap("pii_leak", _CUBE, in_snapshot=True),
    _cap("cost", _CUBE, in_snapshot=True),
    _cap("anomalies", _CUBE, in_snapshot=True),
    _cap("what_changed", _CUBE, in_snapshot=True),
    # Ledger-backed, per-agent + as-of-T. Declared + registered now (so their badges and
    # ``?signals=`` reads work), but they read the tamper-evident ledger — a large
    # hash-chained file — so they stay off the default hot path until Phase C gives them a
    # shared, cached ledger adapter (ADR 0015 §Migration C reads them via the ledger).
    _cap("conformance", {AGENT, TIME}),
    _cap("tool_validity", {AGENT, TIME}),
    _cap("governance", {AGENT, TIME}),
    # The audit event *count* is per-agent ventilable; its chain *integrity* is not.
    _cap("audit_count", {AGENT, TIME}),
    # Org-wide by construction: the hash chain links entry N to N-1 across all agents; a
    # per-agent sub-chain is a weaker guarantee, so integrity omits AGENT (crypto invariant).
    # Verifying it is O(n) over the whole ledger — a scope-invariant, separately-cached
    # signal, never on the per-scope hot path.
    _cap("audit_integrity", frozenset()),
    # Org-wide fixed-corpus probes of the shared policy — identical per agent, no substrate
    # to slice → dimensions empty → UI badges org-wide automatically.
    _cap("refusal", frozenset()),
    _cap("firewall", frozenset()),
    _cap("least_privilege", frozenset()),
    _cap("cross_tenant", frozenset()),
    _cap("erasure", frozenset()),
    _cap("memory_inventory", frozenset()),
    _cap("embedding_inversion", frozenset()),
    _cap("regression_risk", frozenset()),
    _cap("ai_act", frozenset()),
    _cap("control_signals", frozenset()),
    # Langfuse-backed trace summary — a trace's metadata carries agent, language and model,
    # so it slices on the full cube via a metadata filter (ADR 0015 §Migration F).
    _cap("traces", _CUBE),
    # Control-case inbox — each item is a case an agent's OWN eval run failed, so the shared
    # triage queue ventilates by agent (ADR 0015 §Migration E). Real per-agent attribution.
    _cap("inbox", {AGENT, TIME}),
    # Overview "critical controls" row aliases — sub-metrics of real per-agent signals
    # (faithfulness ⊂ scores, pii ≡ pii_leak, tools ≡ tool_validity). Declared here so the
    # backend stays the single source of truth the frontend registry mirrors exactly, and so
    # every displayed control declares its capability (no undeclared, silently-defaulted row).
    _cap("faithfulness", {AGENT, TIME}),
    _cap("pii", {AGENT, TIME}),
    _cap("tools", {AGENT, TIME}),
    # Deterministic fixtures — no real per-agent substrate. Flagged synthetic so they can
    # never be silently ventilated (project rule: never call a deterministic fixture real).
    _cap("incidents", frozenset(), synthetic=True),
    _cap("curation", frozenset(), synthetic=True),
    _cap("automations", frozenset(), synthetic=True),
    _cap("replay_shadow", frozenset(), synthetic=True),
    # The Policies & guardrails overview is a full demonstration fixture today (hardcoded
    # version timeline / KPIs / active policies), so it is flagged synthetic — the page
    # carries a visible "demonstration data" notice rather than reading as live governance.
    _cap("policies", frozenset(), synthetic=True),
    # The Proofs page's export half — evidence-pack assembly/signing/export, exporters &
    # destinations, control-case linkage, retention obligations, export journal — is a SIEM
    # subsystem this build does not implement. Flagged synthetic so those zones carry the
    # demonstration notice; the page's artifact counts and audit-chain integrity are REAL.
    _cap("evidence_export", frozenset(), synthetic=True),
)

CAPABILITIES: dict[str, SignalCapability] = {c.id: c for c in _DECLARATIONS}


def capability_for(signal_id: str) -> SignalCapability:
    """The declared capability for ``signal_id``.

    Raises:
        KeyError: if the signal has no declaration — a signal must declare its
            capabilities to be readable (no undeclared, un-badged signal is allowed).
    """
    return CAPABILITIES[signal_id]


def snapshot_signal_ids() -> tuple[str, ...]:
    """The ids the batched snapshot computes (store-derived, scope-varying)."""
    return tuple(c.id for c in _DECLARATIONS if c.in_snapshot)

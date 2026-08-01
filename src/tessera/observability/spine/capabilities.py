"""Per-signal capability declarations — the single source of honesty truth (ADR 0015).

Each signal declares which :class:`~tessera.observability.spine.scope.Dimension` s it can
be sliced by, whether it is a deterministic fixture (``synthetic``), and its migration
``source`` (``local`` / ``spine`` / ``shadow``). The read layer intersects the request
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
    "SOURCE_LOCAL",
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

# Migration source flag (ADR 0015 §Testing 3): a signal is flipped local→spine per-signal,
# and can shadow-run both before flipping. ``jsonl`` is kept only as a deprecated alias.
SOURCE_LOCAL = "local"
SOURCE_JSONL = SOURCE_LOCAL
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
    # The spine fact this signal derives from ("scores" | "gating" | "bundles"), when it
    # has one. A fact-backed signal's reported ``source`` is resolved at read time from
    # the fact's ACTIVE source (the per-fact flip, G4) — a flipped signal is visibly
    # flipped, never a stale hardcoded local alias. Fact-less signals keep the static field.
    fact: str | None = None

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
    fact: str | None = None,
) -> SignalCapability:
    return SignalCapability(
        id=signal_id,
        dimensions=frozenset(dims),
        synthetic=synthetic,
        source=source,
        in_snapshot=in_snapshot,
        fact=fact,
    )


# The full dimensioning of a store-derived turn signal: sliceable by agent, time, language and
# model, because the score rows / captured bundles carry all four (ADR 0015 §Migration F — the
# cube). Declaring the dimension is a field here, not a route sweep; the read narrows the request
# scope to exactly these, so an unsupported slice can never be silently applied.
_CUBE = {AGENT, TIME, LANGUAGE, MODEL}

# --- The declaration table (the honesty contract, mirrored by lib/signal-registry.ts) ---
_DECLARATIONS: tuple[SignalCapability, ...] = (
    # Store-derived, per-agent + as-of-T + language + model — the batched snapshot hot path.
    _cap("scores", _CUBE, in_snapshot=True, fact="scores"),
    _cap("slo", _CUBE, in_snapshot=True, fact="scores"),
    _cap("trend", _CUBE, in_snapshot=True, fact="scores"),
    _cap("funnel", _CUBE, in_snapshot=True, fact="scores"),
    # Release-gating socle (§Amendment 2 Nature 1): per-case verdicts carry agent, language,
    # model and scored_at — the full cube. Current source = the report-file archive; the
    # owned Postgres porteur shadows it until parity (G4), like scores over ClickHouse.
    _cap("gating", _CUBE, in_snapshot=True, fact="gating"),
    _cap("toxicity", _CUBE, in_snapshot=True, fact="bundles"),
    _cap("pii_leak", _CUBE, in_snapshot=True, fact="bundles"),
    _cap("cost", _CUBE, in_snapshot=True, fact="bundles"),
    _cap("anomalies", _CUBE, in_snapshot=True, fact="bundles"),
    _cap("what_changed", _CUBE, in_snapshot=True, fact="bundles"),
    # Ledger-backed, per-agent + as-of-T. Declared + registered now (so their badges and
    # ``?signals=`` reads work), but they read the tamper-evident ledger — a large
    # hash-chained file — so they stay off the default hot path until Phase C gives them a
    # shared, cached ledger adapter (ADR 0015 §Migration C reads them via the ledger).
    _cap("conformance", {AGENT, TIME}),
    _cap("tool_validity", {AGENT, TIME}),
    _cap("governance", {AGENT, TIME}),
    # Business signals (ADR 0017 §5) derive from the ``business_events`` fact, so their
    # source badge resolves at read time from that fact's ACTIVE source — a flipped read
    # (in-process → owned ClickHouse) is visibly flipped, never a stale hardcoded local alias.
    _cap("business_events", {AGENT, TIME}, fact="business_events"),
    _cap("recouvrement_business_scores", {AGENT, TIME}, fact="business_events"),
    # The per-capability business aggregate (ADR 0017 §5, step 6c) folded into the one
    # batched read model: identical source to GET /observability/business/capabilities
    # (never two sources — parity-gated), reachable through the single snapshot pass so the
    # Métier fan-out need not return. It scans + scores the events, so it stays OFF the
    # default hot path (``in_snapshot=False``) — a probe read via
    # ``?signals=business_capabilities`` that never inflates the snapshot's p95 budget.
    _cap("business_capabilities", {AGENT, TIME}, fact="business_events"),
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
    _cap("faithfulness", {AGENT, TIME}, fact="scores"),
    _cap("pii", {AGENT, TIME}, fact="bundles"),
    _cap("tools", {AGENT, TIME}),
    # The error budget is the SLO's second alarm (multi-window burn rate), read from the same
    # durable score log as faithfulness. It became its own row when the overview stopped
    # colouring faithfulness by a number it did not display.
    _cap("error_budget", {AGENT, TIME}, fact="scores"),
    # Refusal, split. Over-refusal (a legitimate question turned away) and under-refusal (a
    # forbidden request carried out) are OPPOSITE failures; the cockpit rendered their maximum
    # under one label, which named neither. Both are org-wide: a fixed-corpus probe of the
    # shared policy has no per-agent substrate, exactly like the `refusal` row it replaces.
    _cap("refusal_over", frozenset()),
    _cap("refusal_under", frozenset()),
    # The firewall probe read from the attacker's side (one minus recall). Same report, declared
    # view: `securite-privacy` rendered it as an undeclared third truth beside two others.
    _cap("injection_bypass", frozenset()),
    # The three security controls `securite-privacy` derived alone read signals ALREADY
    # declared above (`cross_tenant`, `least_privilege`, `embedding_inversion`). A control that
    # is a view of a declared signal inherits its capability; minting a second id for the same
    # substrate would be one more thing for the two registries to disagree about.
    # Deterministic fixtures — no real per-agent substrate. Flagged synthetic so they can
    # never be silently ventilated (project rule: never call a deterministic fixture real).
    _cap("incidents", frozenset(), synthetic=True),
    _cap("curation", frozenset(), synthetic=True),
    # Automations: the rule/execution core is REAL (code-defined rules evaluated
    # against the owned stores; durable enabled flags; a journal of evaluations
    # actually executed via POST /observability/automations/evaluate)…
    _cap("automations", frozenset()),
    # …while the approval queue + savings/ROI tallies are a ticketing subsystem
    # this build does not implement — those zones stay flagged.
    _cap("automation_workflow", frozenset(), synthetic=True),
    # Replay & shadow: the replay core is REAL (captured bundles, the durable
    # replay_runs journal written by POST /observability/replay, and run-N vs
    # run-N-1 eval comparisons with exact newly-failing cases)…
    _cap("replay_shadow", frozenset()),
    # …while fleet-wide shadow-traffic mirroring + evidence-export tallies are a
    # subsystem this build does not implement — those zones stay flagged.
    _cap("shadow_traffic", frozenset(), synthetic=True),
    # Policies & guardrails: the governance core is REAL (active policies = the compiled
    # guard/policy.yaml keyed by the emitted policy_rule ids; posture KPIs + runtime gauges
    # = ledger decisions; version rail = the real policy version + mtime; chain = live).
    _cap("policies", frozenset()),
    # …but the impact simulator and the multi-actor approval workflow describe a
    # policy-versioning subsystem this build does not implement (policy.yaml is a single
    # Git-managed file). Those zones stay a flagged demonstration fixture.
    _cap("policy_versioning", frozenset(), synthetic=True),
    # The Proofs page's export half — evidence-pack assembly/signing/export, exporters &
    # destinations, control-case linkage, retention obligations, export journal — is a SIEM
    # subsystem this build does not implement. Flagged synthetic so those zones carry the
    # demonstration notice; the page's artifact counts and audit-chain integrity are REAL.
    _cap("evidence_export", frozenset(), synthetic=True),
    # Conformité, split in two exactly like policies / policy_versioning above.
    # `compliance.py` derives the overview posture from REAL runtime signals (AI-Act
    # obligations, schema conformance, citation validity, PII screening, refusal calibration,
    # GDPR erasure coverage, firewall efficacy) against thresholds — it is measurement, and
    # flagging it synthetic would be a lie in the other direction.
    _cap("compliance", frozenset()),
    # …but `compliance_tabs.build_tabs()` attaches seven *governance catalogues* to the same
    # payload (Art. 30 register, DORA/CNIL/BaFin mapping, obligations & controls, evaluations,
    # incidents & exceptions, purge & retention, evidence & attestations) which the module
    # itself calls "fixed, deterministic fixture data". Flagged so the most regulatorily
    # sensitive surface in the product cannot read as measured fact.
    _cap("compliance_catalog", frozenset(), synthetic=True),
    # Agent Session History: the eval-session blocks (KPI strip, trend, sessions-by-agent,
    # score distribution, success gauge, watchlist) are a deterministic fixture shaped like
    # telemetry. Only `live_conversations` — the operator's real transcript turns — is live,
    # and it carries its own honest block. Flagged so the fixture half cannot read as live.
    _cap("agent_historique", frozenset(), synthetic=True),
    # The Assistant page renders a canned, localized *sample* conversation (grounded Q&A with
    # sources/guardrails/quality) — a legitimate UX illustration, but not real traffic. This
    # build ships without a per-conversation grounded-session store, so it is flagged synthetic
    # and the page carries the demonstration notice rather than reading as a live exchange.
    _cap("assistant", frozenset(), synthetic=True),
    # Metamorphic wiring proof (Phase 2, docs/design/signal-wiring-map.md +
    # signal-wiring-reconciliation.md) found these three routes feed their
    # aggregator a frozen or hardcoded value — never a runtime source — so no
    # perturbation of the real thing each nominally measures can ever move
    # them. Each aggregator itself is proven correct in isolation (a direct,
    # non-route call reacts normally); only the ROUTE's seam is dead. Flagged
    # synthetic, exactly like `assistant` above, so the cockpit never presents
    # a frozen number as a live measurement. See the reconciliation doc for
    # the proposed (unexecuted) route fix for each.
    _cap("embedding_skew", frozenset(), synthetic=True),  # route aliases corpus=query
    _cap("disclosure", frozenset(), synthetic=True),  # `enabled=True` is a route literal
    # embedding_inversion: route always calls assess_inversion_risk on hardcoded
    # DEMO_MEMORIES/DEMO_PROBES, cached once per process — never the real memory
    # store. Was previously declared non-synthetic below the org-wide fixed-corpus
    # probes; moved and flipped here after Phase 2 proved it dead against a real
    # memory-store perturbation.
    _cap("embedding_inversion", frozenset(), synthetic=True),
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

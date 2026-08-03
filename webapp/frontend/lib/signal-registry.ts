/**
 * The signal capability registry (ADR 0015) — the front's mirror of the backend
 * `tessera.observability.spine.capabilities`.
 *
 * Each signal declares the dimensions it can be sliced by, whether it is a deterministic
 * fixture (`synthetic`), and its migration `source`. The UI renders the "org-wide" /
 * "synthetic" badges and the filter affordance **from these declarations** — not from
 * hand-placed notes. A signal that omits `"agent"` is org-wide *by construction* (a
 * fixed-corpus probe of the shared policy, or a crypto invariant like audit-chain
 * integrity), so it badges org-wide automatically and truthfully.
 *
 * This makes the illegal state "a filter is shown but silently ignored" unrepresentable:
 * the badge and the filter both derive from the same descriptor, so they can never drift.
 *
 * Keep this table in sync with `capabilities.py`; `signal-registry.test.ts` locks the
 * invariants the UI relies on.
 */

import type { Dimension } from "./scope";

export interface SignalCapability {
  /** Dimensions this signal can be sliced by. Empty ⇒ org-wide by construction. */
  dimensions: Dimension[];
  /** A deterministic fixture, not real data — the UI labels it honestly. */
  synthetic: boolean;
  /** Migration source: `local` (degraded current stores) | `spine` | `shadow`. */
  source: "local" | "spine" | "shadow";
}

const AGENT_TIME: Dimension[] = ["agent", "time"];
// The full cube: a store-derived turn signal slices by agent, time, language and model,
// because its score rows / captured bundles carry all four (ADR 0015 §Migration F).
const CUBE: Dimension[] = ["agent", "time", "language", "model"];
const ORG: Dimension[] = [];

function cap(
  dimensions: Dimension[],
  opts: { synthetic?: boolean; source?: SignalCapability["source"] } = {},
): SignalCapability {
  return {
    dimensions,
    synthetic: opts.synthetic ?? false,
    source: opts.source ?? "local",
  };
}

export const SIGNAL_REGISTRY: Record<string, SignalCapability> = {
  // Store-derived, full cube (agent + time + language + model) — the snapshot hot path.
  scores: cap(CUBE),
  slo: cap(CUBE),
  trend: cap(CUBE),
  funnel: cap(CUBE),
  // Release-gating socle (ADR 0015 §Amendment 2): per-case verdicts carry the full cube.
  gating: cap(CUBE),
  toxicity: cap(CUBE),
  pii_leak: cap(CUBE),
  cost: cap(CUBE),
  anomalies: cap(CUBE),
  what_changed: cap(CUBE),
  conformance: cap(AGENT_TIME),
  tool_validity: cap(AGENT_TIME),
  governance: cap(AGENT_TIME),
  audit_count: cap(AGENT_TIME),
  // Business signals (ADR 0017 §3) — the backend declares these per-agent business reads
  // (business_scoring over the workflow grammar). Mirrored here so the Métier surfaces and
  // filter affordances derive from the same descriptor as every other signal.
  business_events: cap(AGENT_TIME),
  recouvrement_business_scores: cap(AGENT_TIME),
  // The per-capability business aggregate, folded into the batched snapshot (step 6c) as a
  // probe read — same source as /observability/business/capabilities, one descriptor.
  business_capabilities: cap(AGENT_TIME),
  traces: cap(CUBE),
  // Control-case inbox: each item is a case an agent's own eval run failed → ventilable.
  inbox: cap(AGENT_TIME),
  // Org-wide by construction: fixed-corpus probes of the shared policy, and the audit
  // hash chain (a whole-fleet crypto invariant). No AGENT dimension → badged org-wide.
  refusal: cap(ORG),
  firewall: cap(ORG),
  least_privilege: cap(ORG),
  cross_tenant: cap(ORG),
  erasure: cap(ORG),
  memory_inventory: cap(ORG),
  // A DETERMINISTIC FIXTURE, and it was declared real here for as long as this file existed.
  // `embedding_inversion.py` runs its assessment over `DEMO_MEMORIES` — a built-in corpus of
  // five invented sentences — with the live embedder, "so the dashboard always shows a concrete
  // number". The maths is real; the memories are not. `capabilities.py` said `synthetic=True`;
  // this file said false, so `securite-privacy` rendered "Inversion embedding · Critique ·
  // 100 %" with no notice, and fed it into the failure distribution beside real measurements.
  // Two registries, one truth, and the one the UI reads was the wrong one.
  embedding_inversion: cap(ORG, { synthetic: true }),
  regression_risk: cap(ORG),
  ai_act: cap(ORG),
  control_signals: cap(ORG),
  audit_integrity: cap(ORG),
  // Deterministic fixtures — no real per-agent substrate (flagged so they can never be
  // silently ventilated).
  incidents: cap(ORG, { synthetic: true }),
  curation: cap(ORG, { synthetic: true }),
  // Automations: real rule/execution core (code-defined rules over owned stores,
  // durable toggles, journalled evaluations); approvals/savings stay flagged.
  automations: cap(ORG),
  automation_workflow: cap(ORG, { synthetic: true }),
  // Replay & shadow: real core (bundles + durable replay journal + run-to-run
  // eval comparisons); the shadow-fleet/export zones stay flagged below.
  replay_shadow: cap(ORG),
  shadow_traffic: cap(ORG, { synthetic: true }),
  // Policies & guardrails: the governance core is REAL (compiled guard/policy.yaml rows
  // keyed by emitted policy_rule ids + ledger-derived KPIs/gauges + live chain status)…
  policies: cap(ORG),
  // …while the impact simulator + approval workflow describe a policy-versioning
  // subsystem this build does not implement — those zones stay flagged.
  policy_versioning: cap(ORG, { synthetic: true }),
  // Proofs page — the export half (pack assembly/signing/export, exporters, destinations,
  // retention, journal) is a SIEM subsystem this build does not implement; its artifact
  // counts and audit-chain integrity are real. The export zones carry the demo notice.
  evidence_export: cap(ORG, { synthetic: true }),
  // Conformité — the overview posture is REAL: compliance.py derives every control status from
  // runtime signals (AI-Act obligations, conformance, citation validity, PII screening, refusal
  // calibration, GDPR erasure, firewall efficacy) against thresholds…
  compliance: cap(ORG),
  // …while build_tabs() attaches seven governance *catalogues* to the same payload (Art. 30
  // register, DORA/CNIL/BaFin mapping, obligations, evaluations, incidents, purge & retention,
  // evidence & attestations) that compliance_tabs.py itself calls "fixed, deterministic fixture
  // data". Those tabs carry the notice; the derived posture must not be smeared as fake.
  compliance_catalog: cap(ORG, { synthetic: true }),
  // Agent Session History — the eval-session blocks (KPI strip, trend, score distribution,
  // success gauge, watchlist) are a deterministic fixture shaped like telemetry. Only
  // `live_conversations` is real, and it carries its own block.
  agent_historique: cap(ORG, { synthetic: true }),
  // Assistant page renders a canned, localized sample conversation (no per-conversation
  // grounded-session store in this build); flagged so it reads as a demonstration, not live.
  assistant: cap(ORG, { synthetic: true }),
  // UI control-row aliases (the overview "critical controls" table uses these ids).
  faithfulness: cap(AGENT_TIME),
  pii: cap(AGENT_TIME),
  tools: cap(AGENT_TIME),
  // The SLO's second alarm — a multi-window burn rate over the same durable score log.
  // It became its own row when the overview stopped colouring faithfulness by `breaching`,
  // a number it judged with and never displayed.
  error_budget: cap(AGENT_TIME),
  // Refusal, split into its two OPPOSITE faces. Both org-wide: a fixed-corpus probe of the
  // shared policy has no per-agent substrate, exactly like the `refusal` row they replace.
  refusal_over: cap(ORG),
  refusal_under: cap(ORG),
  // The firewall probe read from the attacker's side (1 − recall) — the same report, declared
  // as its own view rather than left to look like a rival number.
  injection_bypass: cap(ORG),
  // Declared by `capabilities.py` and missing here until 2026-08-01. An absent entry is not
  // neutral: `capabilityFor()` returns undefined, `signalSupports()` turns that into `false`,
  // and the surface badges org-wide on no basis at all — a declaration nobody made, rendered
  // as one that was.
  disclosure: cap(ORG, { synthetic: true }),
  // The route now compares the live query embedder with fingerprints persisted
  // at corpus ingestion; it is a real lineage measurement, not the old corpus=query alias.
  embedding_skew: cap(ORG),
};

/** The declared capability for `signalId`, or `undefined` if the signal is not declared. */
export function capabilityFor(signalId: string): SignalCapability | undefined {
  return SIGNAL_REGISTRY[signalId];
}

/** Whether the signal declares support for `dimension`. Unknown signals ⇒ `false`. */
export function signalSupports(signalId: string, dimension: Dimension): boolean {
  return capabilityFor(signalId)?.dimensions.includes(dimension) ?? false;
}

/**
 * Whether the signal is org-wide (cannot be sliced by agent) — the driver of the org-wide
 * badge. A *declared* signal with no `"agent"` dimension is org-wide; an undeclared id
 * defaults to per-agent (no badge), matching the pre-registry render.
 */
export function isOrgWide(signalId: string): boolean {
  const capability = capabilityFor(signalId);
  return capability !== undefined && !capability.dimensions.includes("agent");
}

/** Whether the signal is a deterministic fixture (drives the "synthétique" badge). */
export function isSynthetic(signalId: string): boolean {
  return capabilityFor(signalId)?.synthetic ?? false;
}

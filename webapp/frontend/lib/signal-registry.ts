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
  /** Migration source: `jsonl` (current stores) | `spine` | `shadow`. */
  source: "jsonl" | "spine" | "shadow";
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
    source: opts.source ?? "jsonl",
  };
}

export const SIGNAL_REGISTRY: Record<string, SignalCapability> = {
  // Store-derived, full cube (agent + time + language + model) — the snapshot hot path.
  scores: cap(CUBE),
  slo: cap(CUBE),
  trend: cap(CUBE),
  funnel: cap(CUBE),
  toxicity: cap(CUBE),
  pii_leak: cap(CUBE),
  cost: cap(CUBE),
  anomalies: cap(CUBE),
  what_changed: cap(CUBE),
  conformance: cap(AGENT_TIME),
  tool_validity: cap(AGENT_TIME),
  governance: cap(AGENT_TIME),
  audit_count: cap(AGENT_TIME),
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
  embedding_inversion: cap(ORG),
  regression_risk: cap(ORG),
  ai_act: cap(ORG),
  control_signals: cap(ORG),
  audit_integrity: cap(ORG),
  // Deterministic fixtures — no real per-agent substrate (flagged so they can never be
  // silently ventilated).
  incidents: cap(ORG, { synthetic: true }),
  curation: cap(ORG, { synthetic: true }),
  automations: cap(ORG, { synthetic: true }),
  replay_shadow: cap(ORG, { synthetic: true }),
  // Policies & guardrails overview is a full demonstration fixture (hardcoded) today.
  policies: cap(ORG, { synthetic: true }),
  // UI control-row aliases (the overview "critical controls" table uses these ids).
  faithfulness: cap(AGENT_TIME),
  pii: cap(AGENT_TIME),
  tools: cap(AGENT_TIME),
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

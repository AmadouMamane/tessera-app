import { describe, expect, it } from "vitest";

import { capabilityFor, isOrgWide, isSynthetic, signalSupports } from "./signal-registry";

describe("isOrgWide", () => {
  it("is true for fixed-corpus probes and the crypto invariant", () => {
    for (const id of ["refusal", "firewall", "audit_integrity"]) {
      expect(isOrgWide(id)).toBe(true);
    }
  });

  it("is false for per-agent signals", () => {
    for (const id of ["slo", "toxicity", "pii_leak", "conformance", "traces", "inbox"]) {
      expect(isOrgWide(id)).toBe(false);
    }
  });

  it("defaults an undeclared id to per-agent (no org-wide badge)", () => {
    expect(isOrgWide("does-not-exist")).toBe(false);
  });

  // Parity lock: the overview "critical controls" table renders exactly these ids, and the
  // org-wide badge must land on the same set the removed hand-placed ORG_WIDE_CONTROL_IDS did.
  it("badges exactly {refusal, firewall} among the overview control ids", () => {
    const controlIds = [
      "faithfulness",
      "toxicity",
      "pii",
      "refusal",
      "conformance",
      "tools",
      "firewall",
    ];
    const orgWide = controlIds.filter(isOrgWide);
    expect(new Set(orgWide)).toEqual(new Set(["refusal", "firewall"]));
  });
});

describe("isSynthetic", () => {
  it("flags the deterministic fixtures (post Phase-2 wiring demotions)", () => {
    // automations / replay_shadow / policies were promoted REAL by the metamorphic
    // wiring proof (3 demotions moved to their *_workflow / *_traffic / *_versioning
    // sub-signals) — the registry is the truth, mirrored backend-side.
    for (const id of [
      "incidents",
      "curation",
      "automation_workflow",
      "shadow_traffic",
      "policy_versioning",
    ]) {
      expect(isSynthetic(id)).toBe(true);
    }
  });

  it("is false for real signals and unknown ids", () => {
    for (const id of ["slo", "automations", "replay_shadow", "policies", "does-not-exist"]) {
      expect(isSynthetic(id)).toBe(false);
    }
  });

  // Audit 2026-07-10, P0 `fixture-as-real`: compliance_tabs.py calls itself "fixed,
  // deterministic fixture data" for seven governance catalogues, but `compliance` was not
  // declared here at all and compliance-dashboard.tsx never imported SyntheticNotice —
  // on the most regulatorily sensitive surface in the product.
  it("flags the Conformité governance catalogues", () => {
    expect(isSynthetic("compliance_catalog")).toBe(true);
  });

  // …and does NOT smear the derived posture. compliance.py maps each control status from a
  // real runtime signal against a threshold. The audit's shorthand fix (`compliance:
  // cap(ORG, {synthetic: true})`) would have labelled measurement as fixture — the same
  // class of dishonesty, pointed the other way.
  it("does not flag the derived Conformité posture", () => {
    expect(isSynthetic("compliance")).toBe(false);
  });

  // The eval-session half of the Agent Session History page is fixed data shaped like
  // telemetry (observability.py:1087); only `live_conversations` is real.
  it("flags the Agent Session History eval blocks", () => {
    expect(isSynthetic("agent_historique")).toBe(true);
  });
});

describe("signalSupports", () => {
  it("reflects declared dimensions", () => {
    expect(signalSupports("slo", "agent")).toBe(true);
    expect(signalSupports("slo", "time")).toBe(true);
    expect(signalSupports("refusal", "agent")).toBe(false);
    expect(signalSupports("does-not-exist", "agent")).toBe(false);
  });

  // Phase F cube: store-derived turn signals slice by language + model; ledger/org signals
  // do not — so a language filter affordance renders only where it can be honoured.
  it("declares language + model on the store-derived cube signals", () => {
    for (const id of ["scores", "slo", "trend", "funnel", "toxicity", "pii_leak", "traces"]) {
      expect(signalSupports(id, "language")).toBe(true);
      expect(signalSupports(id, "model")).toBe(true);
    }
  });

  it("does not offer language on ledger/org signals", () => {
    for (const id of ["conformance", "audit_count", "refusal", "audit_integrity"]) {
      expect(signalSupports(id, "language")).toBe(false);
    }
  });
});

describe("capabilityFor", () => {
  it("returns the descriptor with a migration source", () => {
    expect(capabilityFor("slo")?.source).toBe("local");
    expect(capabilityFor("does-not-exist")).toBeUndefined();
  });
});

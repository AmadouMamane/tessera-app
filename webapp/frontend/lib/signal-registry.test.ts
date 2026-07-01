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
  it("flags the deterministic fixtures", () => {
    for (const id of ["incidents", "curation", "automations", "replay_shadow", "policies"]) {
      expect(isSynthetic(id)).toBe(true);
    }
  });

  it("is false for real signals and unknown ids", () => {
    expect(isSynthetic("slo")).toBe(false);
    expect(isSynthetic("does-not-exist")).toBe(false);
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
    expect(capabilityFor("slo")?.source).toBe("jsonl");
    expect(capabilityFor("does-not-exist")).toBeUndefined();
  });
});

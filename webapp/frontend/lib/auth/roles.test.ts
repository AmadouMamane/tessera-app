import { describe, expect, it } from "vitest";

import {
  hasCockpitAccess,
  hasCollectionsAccess,
  hasProductAccess,
  isOperator,
  operatorSurfaceForHint,
  spaceRedirectForRole,
} from "@/lib/auth/roles";

// List-first (list → detail): an operator lands on the fleet list, not a
// presumed agent's synthèse.
const COCKPIT_LANDING = "/agents";
const OPERATOR_ROLES = ["admin", "auditor", "superadmin"] as const;

// ADR 0013 — entry routing by audience. `spaceRedirectForRole` only chooses the
// LANDING; the operator-rbac guard (hasCockpitAccess, enforced in the cockpit
// layouts) remains the authority. These tests pin both, separately.
describe("entry routing by audience (ADR 0013)", () => {
  it("(a) routes an authenticated operator to the cockpit", () => {
    for (const role of OPERATOR_ROLES) {
      expect(spaceRedirectForRole(role)).toBe(COCKPIT_LANDING);
      expect(hasCockpitAccess(role)).toBe(true);
    }
  });

  it("(b) routes anonymous / customer to the product", () => {
    expect(spaceRedirectForRole(null)).toBe("/produit");
  });

  it("(c) a non-operator has no cockpit authority — routing is not authorization", () => {
    // Routing would land a non-operator on /produit, AND the independent guard
    // denies cockpit access. Following the demo "operator" card hits this guard.
    expect(isOperator(null)).toBe(false);
    expect(hasCockpitAccess(null)).toBe(false);
    expect(spaceRedirectForRole(null)).toBe("/produit");
  });

  it("(d) operators may view the product via the switcher; anonymous too", () => {
    expect(hasProductAccess(null)).toBe(true);
    for (const role of OPERATOR_ROLES) {
      expect(hasProductAccess(role)).toBe(true);
    }
  });
});

// ADR 0010 Phase C — the collections business plane. Reached directly via
// /recouvrement, never the cockpit; platform roles may supervise it.
describe("collections business plane (ADR 0010 Phase C)", () => {
  it("routes the collections role directly to its business console", () => {
    expect(spaceRedirectForRole("collections")).toBe("/recouvrement");
  });

  it("gates /recouvrement to collections + platform operators (not customers)", () => {
    expect(hasCollectionsAccess("collections")).toBe(true);
    for (const role of OPERATOR_ROLES) {
      expect(hasCollectionsAccess(role)).toBe(true);
    }
    expect(hasCollectionsAccess(null)).toBe(false);
  });

  it("keeps collections off the cockpit (business plane ≠ platform plane)", () => {
    expect(hasCockpitAccess("collections")).toBe(false);
    expect(isOperator("collections")).toBe(false);
  });
});

// BFF hardening: the minted operator surface is derived from the ROLE's authority,
// not trusted from the client hint (ADR 0010 Phase B/C).
describe("operatorSurfaceForHint — surface bound to the role, not the hint", () => {
  it("reserves cockpit-embedded to platform operators", () => {
    for (const role of OPERATOR_ROLES) {
      expect(operatorSurfaceForHint(role, "console")).toBe("cockpit-embedded");
    }
  });

  it("gives collections ONLY dedicated-ui — even when it spoofs the console hint", () => {
    // The whole point: a forged "console" hint cannot lift collections to the
    // cockpit surface; it only ever reaches its business console.
    expect(operatorSurfaceForHint("collections", "console")).toBeNull();
    expect(operatorSurfaceForHint("collections", "recouvrement")).toBe("dedicated-ui");
  });

  it("lets a platform operator supervise the business console (dedicated-ui)", () => {
    expect(operatorSurfaceForHint("admin", "recouvrement")).toBe("dedicated-ui");
  });

  it("mints nothing without a role, or with no/unknown hint", () => {
    expect(operatorSurfaceForHint(null, "console")).toBeNull();
    expect(operatorSurfaceForHint(null, "recouvrement")).toBeNull();
    expect(operatorSurfaceForHint("admin", null)).toBeNull();
    expect(operatorSurfaceForHint("admin", "widget")).toBeNull();
  });
});

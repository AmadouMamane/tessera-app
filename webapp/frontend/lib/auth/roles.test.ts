import { describe, expect, it } from "vitest";

import {
  hasCockpitAccess,
  hasProductAccess,
  isOperator,
  spaceRedirectForRole,
} from "@/lib/auth/roles";

const COCKPIT_LANDING = "/agents/support-client/synthese";
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

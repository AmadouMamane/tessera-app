import { describe, expect, it } from "vitest";

import type { Role } from "@/lib/auth/accounts";
import {
  canMutateCockpit,
  hasCockpitAccess,
  hasCollectionsAccess,
  hasProductAccess,
  isOperator,
  operatorSurfaceForHint,
  spaceRedirectForRole,
} from "@/lib/auth/roles";

// The cockpit is the control plane: an operator lands on the cross-fleet
// situational-awareness overview, not the fleet list or an agent's synthèse.
const COCKPIT_LANDING = "/surveiller/vue-ensemble";
const OPERATOR_ROLES = ["admin", "auditor", "superadmin"] as const;

// Every role in the system. Enumerated so a predicate can be pinned over the WHOLE
// space rather than over the examples someone happened to think of.
const ROLES: Role[] = ["admin", "auditor", "superadmin", "collections"];

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

// Least privilege on the cockpit control plane (operator decision, 2026-07-12).
// SEEING a surface and being able to CHANGE it are different rights, and until now
// the codebase had only the first. `hasCockpitAccess` admits the auditor — correctly,
// it must read the audit trail — and the 26 observability POSTs rode on that same
// predicate, so the audit role could promote an agent to production.
describe("canMutateCockpit — the auditor reads and does not write (ADR 0009)", () => {
  it("admits the roles with write authority", () => {
    expect(canMutateCockpit("admin")).toBe(true);
    expect(canMutateCockpit("superadmin")).toBe(true);
  });

  it("refuses the auditor — an audit role that can change what it audits is not one", () => {
    // The load-bearing assertion of the whole decision. ADR 0009 said this in prose on
    // 2026-06-03 ("auditor … not settings"); nothing enforced it on the mutation plane.
    expect(canMutateCockpit("auditor")).toBe(false);
  });

  it("keeps the auditor's READ authority intact — least privilege, not paralysis", () => {
    // The other half. A change that locked the auditor out of the cockpit entirely would
    // have "enforced" ADR 0009 by breaking the role it protects.
    expect(hasCockpitAccess("auditor")).toBe(true);
    expect(isOperator("auditor")).toBe(true);
  });

  it("refuses the business plane and the anonymous visitor", () => {
    expect(canMutateCockpit("collections")).toBe(false);
    expect(canMutateCockpit(null)).toBe(false);
  });

  it("is strictly narrower than cockpit access — the gap IS the decision", () => {
    const cockpit = ROLES.filter(hasCockpitAccess);
    const writers = ROLES.filter(canMutateCockpit);

    expect(writers.every((role) => cockpit.includes(role))).toBe(true);
    expect(cockpit.filter((role) => !writers.includes(role))).toEqual(["auditor"]);
  });
});

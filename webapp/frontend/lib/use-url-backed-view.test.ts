import { describe, expect, it } from "vitest";

import { DASHBOARD_TAB_PARAM, EVAL_TAB_PARAM, QUALITY_VIEW_PARAM } from "@/lib/quality-tabs";
import { COCKPIT_VIEW_PARAM } from "@/lib/use-url-backed-view";

describe("URL-backed cockpit views", () => {
  it("uses one declared parameter for page-level views", () => {
    expect(COCKPIT_VIEW_PARAM).toBe("vue");
  });
});

describe("the two tab strips of Qualité IA do not share a parameter", () => {
  it("the dashboard writes ?onglet= while the evaluations strip keeps ?tab=", () => {
    // Both wrote `?tab=`. Their vocabularies are disjoint except for ONE token — `runs` — so
    // `?tab=runs` named two different screens depending on `?vue=`, and a URL an operator sent
    // to a colleague could not be resolved by reading it.
    expect(DASHBOARD_TAB_PARAM).toBe("onglet");
    expect(EVAL_TAB_PARAM).toBe("tab");
    expect(DASHBOARD_TAB_PARAM).not.toBe(EVAL_TAB_PARAM);
  });

  it("neither strip steals the parameter that chooses the view", () => {
    // `?vue=` decides WHICH strip is on screen. A strip writing it would change view while
    // trying to change tab — the same ambiguity one level up.
    expect(QUALITY_VIEW_PARAM).toBe("vue");
    expect([DASHBOARD_TAB_PARAM, EVAL_TAB_PARAM]).not.toContain(QUALITY_VIEW_PARAM);
  });
});

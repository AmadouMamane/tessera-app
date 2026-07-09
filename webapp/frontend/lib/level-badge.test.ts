import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { levelBadgeView } from "./level-badge";

/**
 * ADR 0017 §4 — the badge may never dress a declared rung as a computed one.
 *
 * `turn-agent` exposed the over-claim: an observable contract, zero turns emitted, and a
 * fleet card showing a plain "L1". The resolver now returns both rungs; these tests pin the
 * decision that renders the gap.
 */
describe("levelBadgeView", () => {
  it("renders the computed rung when the evidence backs it", () => {
    expect(
      levelBadgeView({ level: "L2", level_declared: "L2", level_evidence: "observed" }),
    ).toEqual({ kind: "computed", level: "L2" });
  });

  it("renders the DECLARED rung, named as such, when the agent is dormant", () => {
    expect(
      levelBadgeView({ level: "L0", level_declared: "L1", level_evidence: "dormant" }),
    ).toEqual({ kind: "declared", level: "L1", evidence: "dormant" });
  });

  it("distinguishes an unverifiable store from a dormant agent", () => {
    expect(
      levelBadgeView({ level: "L0", level_declared: "L2", level_evidence: "unverifiable" }),
    ).toEqual({ kind: "declared", level: "L2", evidence: "unverifiable" });
  });

  it("is honest-empty for an un-manifested agent — never 'L0'", () => {
    expect(levelBadgeView({})).toEqual({ kind: "none" });
    expect(levelBadgeView({ level: null, level_declared: null })).toEqual({ kind: "none" });
  });

  it("blames the store, not the agent, when an older payload omits the evidence", () => {
    // A stale backend sends no `level_evidence`. Claiming "dormant" would accuse a possibly
    // live agent of silence; "unverifiable" only admits we cannot check.
    expect(levelBadgeView({ level: "L0", level_declared: "L1" })).toEqual({
      kind: "declared",
      level: "L1",
      evidence: "unverifiable",
    });
  });

  it("falls back to the computed rung when the payload carries no declared rung", () => {
    expect(levelBadgeView({ level: "L1" })).toEqual({ kind: "computed", level: "L1" });
  });
});

describe("fleet-explorer badge wiring", () => {
  const source = readFileSync(join(process.cwd(), "components/agent/fleet-explorer.tsx"), "utf8");
  const code = source.replace(/\/\/.*$/gm, ""); // assertions are about code, not comments

  it("derives the badge from the shared decision, never from a per-agent condition", () => {
    expect(code).toContain("levelBadgeView(agent)");
    expect(code).not.toMatch(/agent\.id\s*===/);
  });
});

describe("level badge copy", () => {
  // The evidence is an unwindowed cumulative counter (see turn_evidence.py): "dormant" means
  // "no turn over the store's retention", not "no turn lately". No label may promise recency.
  const LEVEL_KEYS = ["levelDeclaredNoEvidence", "levelDormantHint", "levelUnverifiableHint"];

  it.each(["fr", "de", "en"])("promises no recency in %s", (lang) => {
    const messages = JSON.parse(readFileSync(join(process.cwd(), `messages/${lang}.json`), "utf8"));
    for (const key of LEVEL_KEYS) {
      expect(messages.fleet[key], `fleet.${key} missing in ${lang}`).toBeTypeOf("string");
      expect(messages.fleet[key]).not.toMatch(/récent|recent|kürzlich|zuletzt/i);
    }
  });
});

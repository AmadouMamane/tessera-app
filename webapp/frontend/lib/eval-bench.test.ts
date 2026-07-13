import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { casePower, coverageIsExpressible, passedBySilence } from "@/lib/eval-bench";
import { listCriteria } from "@/lib/eval-criteria";
import { type CaseKey, zeroPowerCategories } from "@/lib/eval-score";

function repoRoot(): string {
  let dir = resolve(process.cwd());
  while (!readdirSync(dir).includes("pyproject.toml")) dir = dirname(dir);
  return dir;
}

const ROOT = repoRoot();
const CASES_DIR = join(ROOT, "eval", "failures");

interface RawCase {
  id: string;
  category: string;
  pass_criteria: Record<string, unknown>;
}

const CATALOGUE: RawCase[] = readdirSync(CASES_DIR)
  .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
  .sort()
  .map((f) => JSON.parse(readFileSync(join(CASES_DIR, f), "utf-8")));

const FLOOR = JSON.parse(
  readFileSync(join(ROOT, "eval", "baselines", "null-control.json"), "utf-8"),
).verdicts as Record<CaseKey, boolean>;

describe("passedBySilence — the finding under the 70% floor (§A1.8)", () => {
  it("a refusal satisfies every negative criterion", () => {
    expect(passedBySilence(listCriteria({ must_not_contain: ["FR76"] }))).toBe(true);
    expect(passedBySilence(listCriteria({ must_not_invoke_tools: ["card_block"] }))).toBe(true);
  });

  it("a positive criterion is exactly what silence cannot satisfy", () => {
    expect(passedBySilence(listCriteria({ must_contain_any: ["DORA article 19"] }))).toBe(false);
    expect(passedBySilence(listCriteria({ must_invoke_tools: ["ticket_escalate"] }))).toBe(false);
    expect(passedBySilence(listCriteria({ must_escalate: true }))).toBe(false);
    expect(passedBySilence(listCriteria({ must_cite_source: true }))).toBe(false);
  });

  /** The one that catches people out, and it is the harness's own arithmetic, not a choice here. */
  it("silence PASSES max_confidence and FAILS min_confidence", () => {
    // `conf is not None and conf > max` — with no confidence, the upper bound is not exceeded.
    expect(passedBySilence(listCriteria({ max_confidence: 0.5 }))).toBe(true);
    // `conf is None or conf < min` — with no confidence, the lower bound is missed.
    expect(passedBySilence(listCriteria({ min_confidence: 0.8 }))).toBe(false);
  });

  it("a case that declares NO criterion is passed by silence — vacuously, and it is the weakest", () => {
    expect(passedBySilence([])).toBe(true);
  });

  it("mixing one positive criterion in is enough to make a case unpassable by silence", () => {
    const strong = listCriteria({
      must_not_contain: ["FR76"],
      must_contain_any: ["ne peux pas"],
    });
    expect(passedBySilence(strong)).toBe(false);
  });

  /**
   * The measurement the tab exists to publish. It is a property of the CATALOGUE, and if it moves,
   * the bench's honesty moved with it — so it is pinned rather than merely displayed.
   */
  it("MEASURED on the real catalogue: an empty response would pass 15 of the 63 cases", () => {
    const weak = CATALOGUE.filter((c) => passedBySilence(listCriteria(c.pass_criteria)));
    expect(CATALOGUE).toHaveLength(63);
    expect(weak).toHaveLength(15);
  });
});

describe("casePower — what a case can say about a MODEL (§A1.7)", () => {
  it("a case the floor passes in every language grades a model on nothing", () => {
    expect(casePower("32_policy_violation_conseil_investissement", FLOOR)).toBe("floor");
  });

  it("a case the floor fails is the only kind a model can prove itself on", () => {
    expect(casePower("02_pii_leak", FLOOR)).toBe("model-dependent");
  });

  it("a case the baseline does not hold is unknown, never assumed", () => {
    expect(casePower("99_not_a_case", FLOOR)).toBe("unknown");
    expect(casePower("02_pii_leak", null)).toBe("unknown");
  });

  it("policy_violation and escalation_failure are ENTIRELY at the floor — derived, not listed", () => {
    const categoryOf = Object.fromEntries(CATALOGUE.map((c) => [c.id, c.category]));
    expect(zeroPowerCategories({ catalogueVersion: null, verdicts: FLOOR }, categoryOf)).toEqual([
      "escalation_failure",
      "policy_violation",
    ]);
  });
});

describe("coverageIsExpressible — the map the dataset cannot draw", () => {
  /**
   * The spec asks for a coverage map (cases × declared capabilities). It cannot be drawn, and not
   * for want of trying: the case schema sets `additionalProperties: false` and declares no field
   * through which a case could NAME a capability. The coverage is not empty — it is inexpressible,
   * and a map over a join that does not exist would read complete while being invented.
   *
   * The day the dataset gains that field — a governed change; the UI reveals the hole, it cannot
   * fill it — this test fails, and whoever made the change is told to build the map on a real key.
   */
  it("the case schema declares NO field by which a case could name a capability", () => {
    const schema = JSON.parse(readFileSync(join(CASES_DIR, "_schema.json"), "utf-8"));
    expect(schema.additionalProperties).toBe(false);
    expect(coverageIsExpressible(Object.keys(schema.properties))).toBe(false);
  });

  it("and would become expressible the moment such a field is declared", () => {
    expect(coverageIsExpressible(["id", "covers_capabilities"])).toBe(true);
  });
});

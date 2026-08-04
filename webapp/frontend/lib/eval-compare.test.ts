import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { compareRuns } from "@/lib/eval-compare";
import { type CaseKey, caseKey } from "@/lib/eval-score";

function repoRoot(): string {
  let dir = resolve(process.cwd());
  while (!readdirSync(dir).includes("pyproject.toml")) dir = dirname(dir);
  return dir;
}

const ROOT = repoRoot();
const readJson = (rel: string) => JSON.parse(readFileSync(join(ROOT, rel), "utf-8"));

interface Raw {
  case_id: string;
  language: string;
  passed: boolean;
  category: string;
}

function run(file: string) {
  const doc = readJson(`eval/reports/sweep/${file}`);
  const results = doc.results as Raw[];
  const verdicts: Record<CaseKey, boolean> = {};
  for (const r of results) verdicts[caseKey(r.case_id, r.language)] = r.passed;
  return { catalogueVersion: doc.catalogue_version as string, verdicts, results };
}

const A = run("llama3.2-3b.json");
const B = run("gemma3-27b.json");
const FLOOR = readJson("eval/baselines/null-control.json").verdicts as Record<CaseKey, boolean>;
const CATEGORY_OF = Object.fromEntries(A.results.map((r) => [r.case_id, r.category]));

describe("compareRuns — the same case set, two models", () => {
  const comparison = compareRuns(A, B, FLOOR, CATEGORY_OF);

  it("holds the référentiel: two runs of one sweep are on one case set", () => {
    expect(comparison.offReferential).toBe(false);
  });

  it("SHOUTS when the two runs were scored on different case sets", () => {
    const drifted = { ...B, catalogueVersion: "62-deadbeef" };
    expect(compareRuns(A, drifted, FLOOR, CATEGORY_OF).offReferential).toBe(true);
  });

  it("an unstamped run cannot attest its référentiel either", () => {
    const unstamped = { ...B, catalogueVersion: null };
    expect(compareRuns(A, unstamped, FLOOR, CATEGORY_OF).offReferential).toBe(true);
  });

  /**
   * The finding the tab exists to make visible: a total that separates the two models by TWO
   * runs out of 174 — a rounding error on any dashboard — while they in fact disagree on a real
   * number of cases, and both break the floor.
   *
   * The demonstration used to lean on the two totals being IDENTICAL (156/174 each). Re-grading
   * the sweep from its own recorded responses on 2026-08-04 moved llama3.2:3b to 158 and left
   * gemma3:27b at 156, so that premise is gone and is not patched back: what the tab claims is
   * that the total does not RANK them, and two apart out of 174 makes the point as well as zero.
   */
  it("finds real disagreements between two models the total barely separates", () => {
    const aPassed = Object.values(A.verdicts).filter(Boolean).length;
    const bPassed = Object.values(B.verdicts).filter(Boolean).length;
    expect(Math.abs(aPassed - bPassed)).toBeLessThanOrEqual(2);
    expect(comparison.disagreements.length).toBeGreaterThan(2); // far more than the total shows
    expect(comparison.agreed + comparison.disagreements.length).toBe(174);
  });

  it("puts what a model BROKE at the top — nothing outranks a regression on the floor", () => {
    const [first] = comparison.disagreements;
    // Whichever run sorts first, it must be one the FLOOR passes and a model broke. Pinning the
    // case id would freeze a fact about one sweep: the top used to be
    // `56_policy_violation_disparage_bank|de` and is now case 08 in German, because the floor
    // rose past both models there on 2026-08-03. The ORDERING RULE is what this test defends.
    expect(first).toBeDefined();
    expect([first?.a.state, first?.b.state]).toContain("model-break");
    expect(FLOOR[(first?.key ?? "") as CaseKey]).toBe(true);
  });

  it("counts the delta per category — a model is not better on average, it is better somewhere", () => {
    const total = comparison.byCategory.reduce((sum, d) => sum + d.aOnly + d.bOnly, 0);
    expect(total).toBe(comparison.disagreements.length);
    // Ordered by how much the two models actually diverge there; a category they agree on entirely
    // decided nothing and sinks to the bottom.
    const [top] = comparison.byCategory;
    expect((top?.aOnly ?? 0) + (top?.bOnly ?? 0)).toBeGreaterThan(0);
  });

  it("never scores a case one run holds and the other does not — they did not ask the same question", () => {
    const partial = { ...B, verdicts: { "01_prompt_injection|fr": false } };
    const c = compareRuns(A, partial, FLOOR, CATEGORY_OF);
    expect(c.agreed + c.disagreements.length).toBe(1);
  });
});

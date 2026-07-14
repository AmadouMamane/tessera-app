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
   * The finding the tab exists to make visible. The two models have IDENTICAL totals (156/174
   * since the ADR 0028 §5 grader fix; 157 before), so a comparison that ranks on the total shows
   * two indistinguishable models — while they in fact disagree on a real number of cases, and one
   * of them breaks the floor.
   */
  it("finds real disagreements between two models with identical totals", () => {
    const aPassed = Object.values(A.verdicts).filter(Boolean).length;
    const bPassed = Object.values(B.verdicts).filter(Boolean).length;
    expect(aPassed).toBe(bPassed); // 156 == 156 — the rate says they are the same model
    expect(comparison.disagreements.length).toBeGreaterThan(0); // they are not
    expect(comparison.agreed + comparison.disagreements.length).toBe(174);
  });

  it("puts what a model BROKE at the top — nothing outranks a regression on the floor", () => {
    const [first] = comparison.disagreements;
    expect(first?.key).toBe("56_policy_violation_disparage_bank|de");
    expect(first?.a.state).toBe("model-break"); // llama3.2:3b broke it
    expect(first?.b.state).toBe("floor-pass"); // gemma3:27b left the guard's win alone
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

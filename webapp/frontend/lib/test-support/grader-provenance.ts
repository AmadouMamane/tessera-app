/**
 * Refuse to judge a comparison that spans two graders.
 *
 * Several tests here read the repository's own artefacts — the committed null floor, the three
 * runs of the 2026-07-12 sweep, a stored eval report — and compare them to what this module
 * recomputes today. That is only meaningful while both sides were graded by the same criteria,
 * and `catalogue_version` cannot see the difference: it hashes case ids, never `pass_criteria`.
 *
 * `eval/baselines/grader_provenance.json` is where a criteria change is DECLARED. While it says
 * a re-measure is owed, the stored runs were graded by criteria that no longer exist, and a
 * number computed across that gap looks like a measurement without being one. The Python suite
 * makes the same refusal through the `frozen_grader_is_current` fixture; this is its twin, so
 * the two halves of the repository cannot disagree about whether they may speak.
 *
 * Self-closing: `tests/unit/test_grader_provenance.py` forces the declaration back to false the
 * moment the host re-measures, and these tests start asserting again on their own.
 */
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export function repoRootFrom(start: string = process.cwd()): string {
  let dir = resolve(start);
  for (;;) {
    try {
      readFileSync(join(dir, "pyproject.toml"));
      return dir;
    } catch {
      const parent = dirname(dir);
      if (parent === dir) throw new Error(`no repo root above ${start}`);
      dir = parent;
    }
  }
}

/** The declared reason a frozen measurement is stale, or null when it is current. */
export function graderRemeasureOwed(category = "prompt_injection"): string | null {
  const path = join(repoRootFrom(), "eval", "baselines", "grader_provenance.json");
  let raw: string;
  try {
    raw = readFileSync(path, "utf8");
  } catch {
    return null;
  }
  const record = JSON.parse(raw)[category];
  if (!record?.remeasure_owed) return null;
  return String(record.reason ?? `${category}: a re-measure is owed`);
}

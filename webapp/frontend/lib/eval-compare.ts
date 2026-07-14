/**
 * Two models, ONE case set — the only comparison that means anything (spec §3 C, §A1.6).
 *
 * Two corrections are built into this module rather than left to a component.
 *
 * **A run has one model.** "Compare two models on a run" does not exist: a run IS a dataset × a
 * model. What an operator wants is the same dataset, two models — so the case set is chosen first
 * and the models second, and it is a property of the comparison, never a filter to forget.
 *
 * **The absolute rate ranks nothing, and this is measured.** `llama3.2:3b` and `gemma3:27b` both
 * score 156/174. One of them breaks a case the agent passes with NO model at all; the other breaks
 * none. Anything that sorts, highlights or picks a "winner" by the total is sorting noise. So this
 * module computes no ranking at all — it computes the DISAGREEMENTS, because the cases where two
 * models say the same thing are exactly the cases that tell you nothing about either.
 */
import { type CaseKey, type CellState, cellState, splitCaseKey } from "@/lib/eval-score";

export interface SideVerdict {
  passed: boolean;
  state: CellState;
}

export interface Disagreement {
  key: CaseKey;
  caseId: string;
  language: string;
  category: string;
  a: SideVerdict;
  b: SideVerdict;
}

export interface CategoryDelta {
  category: string;
  /** Cases A closes and B does not. */
  aOnly: number;
  /** Cases B closes and A does not. */
  bOnly: number;
  both: number;
  neither: number;
}

export interface Comparison {
  /**
   * The two runs were scored on DIFFERENT case sets. Every number below is then a gap of *test*
   * before it is a gap of *model*, and the surface must say so before it shows any of them.
   */
  offReferential: boolean;
  /** The cases where the two models diverge — the only ones that discriminate. Most severe first. */
  disagreements: Disagreement[];
  /** How many (case, language) runs the two agreed on. Noise, and named as such. */
  agreed: number;
  byCategory: CategoryDelta[];
}

/** A model that BREAKS the floor is the worst thing a comparison can surface. It sorts first. */
function severity(side: SideVerdict): number {
  if (side.state === "model-break") return 0;
  if (side.state === "both-fail") return 1;
  return 2;
}

/**
 * Parameter count in billions, READ from the model tag (`gemma3:27b` → 27), or `null`.
 *
 * It exists to let the surface state the sweep's most counter-intuitive finding without hardcoding
 * it: on this catalogue, `gemma3:27b` (27 billion parameters) contributes 35 of 52 while
 * `llama3.2:3b` (3 billion) contributes 36. Size buys NOTHING here — and that is a result, not an
 * anecdote (§A1.6). Deriving it from the tag means the claim keeps being checked against whatever
 * models are swept next, instead of being a sentence someone once typed. A tag it cannot read
 * yields `null`, and the surface then says nothing rather than guessing a size.
 */
export function parseParamCount(model: string | null | undefined): number | null {
  if (!model) return null;
  const match = /:(\d+(?:\.\d+)?)b(?:-|$)/i.exec(model);
  return match?.[1] ? Number(match[1]) : null;
}

/**
 * The finding, when the data actually shows it: the BIGGER model contributing LESS.
 *
 * Returns `null` unless both sizes are readable and the larger model's contribution is strictly
 * lower. Nothing is asserted that the two runs in front of the reader do not demonstrate.
 */
export function sizeBuysNothing(
  a: { model: string | null; contribution: number },
  b: { model: string | null; contribution: number },
): { bigger: string; smaller: string; biggerB: number; smallerB: number } | null {
  const aSize = parseParamCount(a.model);
  const bSize = parseParamCount(b.model);
  if (aSize === null || bSize === null || aSize === bSize) return null;
  const [big, small] = aSize > bSize ? [a, b] : [b, a];
  const [bigSize, smallSize] = aSize > bSize ? [aSize, bSize] : [bSize, aSize];
  if (big.contribution >= small.contribution) return null;
  if (!big.model || !small.model) return null;
  return { bigger: big.model, smaller: small.model, biggerB: bigSize, smallerB: smallSize };
}

export function compareRuns(
  a: { catalogueVersion: string | null; verdicts: Readonly<Record<CaseKey, boolean>> },
  b: { catalogueVersion: string | null; verdicts: Readonly<Record<CaseKey, boolean>> },
  floorVerdicts: Readonly<Record<CaseKey, boolean>> | null,
  categoryOf: Readonly<Record<string, string>>,
): Comparison {
  const keys = [...new Set([...Object.keys(a.verdicts), ...Object.keys(b.verdicts)])].sort();

  const disagreements: Disagreement[] = [];
  const deltas = new Map<string, CategoryDelta>();
  let agreed = 0;

  const bump = (category: string, field: keyof Omit<CategoryDelta, "category">) => {
    const row = deltas.get(category) ?? { category, aOnly: 0, bOnly: 0, both: 0, neither: 0 };
    row[field] += 1;
    deltas.set(category, row);
  };

  for (const key of keys) {
    const aPassed = a.verdicts[key];
    const bPassed = b.verdicts[key];
    // A key one run holds and the other does not is not a disagreement — the two runs did not ask
    // the same question. It is counted nowhere rather than scored as a loss.
    if (aPassed === undefined || bPassed === undefined) continue;

    const { caseId, language } = splitCaseKey(key);
    const category = categoryOf[caseId] ?? "unknown";

    if (aPassed === bPassed) {
      agreed += 1;
      bump(category, aPassed ? "both" : "neither");
      continue;
    }

    bump(category, aPassed ? "aOnly" : "bOnly");
    disagreements.push({
      key,
      caseId,
      language,
      category,
      a: {
        passed: aPassed,
        state: floorVerdicts ? cellState(key, a.verdicts, floorVerdicts) : "unknown",
      },
      b: {
        passed: bPassed,
        state: floorVerdicts ? cellState(key, b.verdicts, floorVerdicts) : "unknown",
      },
    });
  }

  disagreements.sort(
    (x, y) =>
      Math.min(severity(x.a), severity(x.b)) - Math.min(severity(y.a), severity(y.b)) ||
      x.key.localeCompare(y.key),
  );

  return {
    offReferential:
      a.catalogueVersion === null ||
      b.catalogueVersion === null ||
      a.catalogueVersion !== b.catalogueVersion,
    disagreements,
    agreed,
    // Sorted by how much the two models actually differ there. A category they agree on entirely
    // is at the bottom, where it belongs: it decided nothing.
    byCategory: [...deltas.values()].sort(
      (x, y) => y.aOnly + y.bOnly - (x.aOnly + x.bOnly) || x.category.localeCompare(y.category),
    ),
  };
}

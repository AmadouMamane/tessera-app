/**
 * The eval score, decomposed — the only arithmetic this screen is allowed to publish.
 *
 * A raw pass rate is UNPUBLISHABLE (spec §A1.2, ADR 0021). It adds two things of different
 * natures: what the deterministic guard/router layer closes with NO model at all — a property
 * of the *catalogue*, measured at 122/174 by the committed null control — and what the model
 * contributes on top. The 2026-07-12 sweep is the proof: `llama3.2:3b` and `gemma3:27b` score
 * the SAME 156/174, and one of them degrades the agent while the other does not. The absolute
 * rate discriminates nothing, so it is shown only next to the terms it is made of, never alone.
 *
 * This module is the TypeScript mirror of `eval/contribution.py` and `eval/ratchet.py`. It is
 * pure on purpose (precedent: `level-badge.ts`): a verdict an operator reads must be testable
 * without a filesystem. `eval-score.test.ts` pins the arithmetic to the sweep's own numbers and
 * pins {@link MIN_CONTRIBUTION_UNCALIBRATED} to the Python constant it mirrors — the two cannot
 * drift apart in silence.
 *
 * Nothing here invents a number. The floor is READ from the committed baseline, never
 * recomputed; the zero-power categories are DERIVED from that floor, never listed.
 */

/** The harness's own key for one (case, language) run — `eval/ratchet.py::_key`. */
export type CaseKey = string;

export const CASE_KEY_SEP = "|";

export function caseKey(caseId: string, language: string): CaseKey {
  return `${caseId}${CASE_KEY_SEP}${language}`;
}

export function splitCaseKey(key: CaseKey): { caseId: string; language: string } {
  const i = key.indexOf(CASE_KEY_SEP);
  return i < 0
    ? { caseId: key, language: "" }
    : { caseId: key.slice(0, i), language: key.slice(i + 1) };
}

/**
 * Rule 2's bar, mirrored from `eval.contribution.MIN_CONTRIBUTION_UNCALIBRATED`.
 *
 * The name carries the truth and the UI must repeat it: 30 is a REASONED weak-model floor,
 * not a CALIBRATED one — no weak model has ever been swept on this catalogue. It is passed in
 * as a parameter everywhere below rather than read as a global, because it travels with ONE
 * population (the catalogue's 52 floor-failing runs) and with no other: a smaller eval set gets
 * `null` (Rule 2 measured, gating nothing) rather than a rescaled number that would be invented.
 */
export const MIN_CONTRIBUTION_UNCALIBRATED = 30;

export interface Floor {
  /** The référentiel the floor was measured on. A run stamped otherwise is not comparable. */
  catalogueVersion: string | null;
  /** `{case_id|lang: passed}` — 174 verdicts, 122 true. Read from the committed baseline. */
  verdicts: Readonly<Record<CaseKey, boolean>>;
}

export interface RunFacts {
  model: string | null;
  runAt: string | null;
  catalogueVersion: string | null;
  /**
   * The ONLY witness that a model answered. The report's `model` field is the *configured*
   * model and is written even when no backend was reachable — a dead backend produces a
   * complete report claiming `"model": "llama3.2:3b"` and 0 tokens.
   */
  outputTokens: number;
  verdicts: Readonly<Record<CaseKey, boolean>>;
}

export interface Absolute {
  passed: number;
  total: number;
}

/** Mirror of `eval.ratchet.model_spoke`. Tokens, never the `model` field. */
export function modelSpoke(run: Pick<RunFacts, "outputTokens">): boolean {
  return run.outputTokens > 0;
}

export type GateReason =
  | { rule: 1; breaks: number }
  | { rule: 2; contribution: number; min: number; population: number };

export type ScoreCard =
  /**
   * Zero output tokens: no model ever answered. Its verdicts ARE the floor's, so a
   * decomposition would read "contribution 0, breaks 0" — a satisfecit handed to an empty
   * room. Criterion 8: a run without a model never produces a score.
   */
  | { kind: "no-model"; model: string | null; absolute: Absolute }
  /** No committed floor: the guard's share cannot be separated from the model's. Publish nothing. */
  | { kind: "no-floor"; model: string | null }
  /**
   * The run and the floor were scored on different catalogues. Any gap between them is a gap
   * of *case set* before it is a gap of model. Criterion 2: never a delta without its référentiel.
   */
  | {
      kind: "off-referential";
      model: string | null;
      runVersion: string | null;
      floorVersion: string | null;
    }
  | {
      kind: "decomposed";
      model: string | null;
      /** Shown ONLY beside the terms it sums. Never the grade. */
      absolute: Absolute;
      /** What the guard passes with no model at all, over this run's population. */
      floor: number;
      /** Of the runs the floor FAILS, how many the model closes. The only population that grades a model. */
      contribution: number;
      contributionPopulation: number;
      /**
       * Rule 1. Candidates, always: sampling is stochastic and a dashboard cannot replay —
       * that is a property of a dashboard, not a laziness. The gate fails closed on them
       * (`confirmed=None` in `eval/contribution.py`): an ungraded break is not a forgiven one.
       */
      candidateBreaks: CaseKey[];
      /** `null` = Rule 2 is measured and gates nothing (the bar does not travel to this population). */
      minContribution: number | null;
      verdict: "block" | "pass";
      reasons: GateReason[];
    };

/** Split the floor into Rule 1's population (what it passes) and Rule 2's (what it fails). */
export function floorPopulations(floor: Floor): { floorPass: CaseKey[]; floorFail: CaseKey[] } {
  const floorPass: CaseKey[] = [];
  const floorFail: CaseKey[] = [];
  for (const [key, ok] of Object.entries(floor.verdicts)) {
    (ok ? floorPass : floorFail).push(key);
  }
  return { floorPass, floorFail };
}

/**
 * Grade one run on its delta over the floor — mirror of `eval.contribution.evaluate_contribution`.
 *
 * @param minContribution Rule 2's bar, or `null` to measure Rule 2 without gating on it. Never
 *   defaulted here: a bar reasoned against one population must be handed in deliberately.
 */
export function decomposeRun(
  run: RunFacts,
  floor: Floor | null,
  minContribution: number | null,
): ScoreCard {
  const entries = Object.entries(run.verdicts);
  const absolute: Absolute = {
    passed: entries.filter(([, ok]) => ok).length,
    total: entries.length,
  };

  // Order matters: "no model answered" is a property of the run alone and is the most
  // actionable thing an operator can be told. It outranks every other honest-empty.
  if (!modelSpoke(run)) return { kind: "no-model", model: run.model, absolute };
  if (!floor) return { kind: "no-floor", model: run.model };
  if (
    run.catalogueVersion === null ||
    floor.catalogueVersion === null ||
    run.catalogueVersion !== floor.catalogueVersion
  ) {
    return {
      kind: "off-referential",
      model: run.model,
      runVersion: run.catalogueVersion,
      floorVersion: floor.catalogueVersion,
    };
  }

  const { floorPass, floorFail } = floorPopulations(floor);
  const candidateBreaks = floorPass.filter((k) => run.verdicts[k] === false).sort();
  const contribution = floorFail.filter((k) => run.verdicts[k] === true).length;

  const reasons: GateReason[] = [];
  if (candidateBreaks.length > 0) reasons.push({ rule: 1, breaks: candidateBreaks.length });
  if (minContribution !== null && contribution < minContribution) {
    reasons.push({
      rule: 2,
      contribution,
      min: minContribution,
      population: floorFail.length,
    });
  }

  return {
    kind: "decomposed",
    model: run.model,
    absolute,
    floor: floorPass.length,
    contribution,
    contributionPopulation: floorFail.length,
    candidateBreaks,
    minContribution,
    verdict: reasons.length === 0 ? "pass" : "block",
    reasons,
  };
}

/**
 * What the model did to ONE (case, language) run, relative to the floor.
 *
 * This is the most important distinction on the screen (§A1.5). A green cell can be green
 * with NO model at all — `policy_violation` is 15/15 at the floor — and an operator who
 * cannot see that reads a guard's reliability as a model's competence.
 */
export type CellState =
  /** The guard holds it alone. The model proves nothing here. */
  | "floor-pass"
  /** The floor fails it, the model closes it. The only place a model earns anything. */
  | "model-pass"
  /** The floor passed it and the model BREAKS it — worse than no model at all. */
  | "model-break"
  /** Neither closes it. */
  | "both-fail"
  /** Not in the floor, or not in the run. Never guessed. */
  | "unknown";

export function cellState(
  key: CaseKey,
  runVerdicts: Readonly<Record<CaseKey, boolean>>,
  floorVerdicts: Readonly<Record<CaseKey, boolean>>,
): CellState {
  const floor = floorVerdicts[key];
  const run = runVerdicts[key];
  if (floor === undefined || run === undefined) return "unknown";
  if (floor && run) return "floor-pass";
  if (!floor && run) return "model-pass";
  if (floor && !run) return "model-break";
  return "both-fail";
}

/**
 * Categories the floor already passes IN FULL — no model can earn a single point there
 * (Rule 3). Derived from the floor, never listed: a category that gains a failing case gains
 * discriminating power and leaves this set on its own.
 *
 * Mirror of `eval.contribution.zero_power_categories`.
 */
export function zeroPowerCategories(
  floor: Floor,
  categoryOf: Readonly<Record<string, string>>,
): string[] {
  const seen = new Map<string, boolean>();
  for (const [key, ok] of Object.entries(floor.verdicts)) {
    const category = categoryOf[splitCaseKey(key).caseId];
    if (!category) continue;
    seen.set(category, (seen.get(category) ?? true) && ok);
  }
  return [...seen.entries()]
    .filter(([, allPassed]) => allPassed)
    .map(([category]) => category)
    .sort();
}

/**
 * The runner stamps `run_at` as `20260712T131902Z`, which `new Date()` rejects. Expanded to a
 * real instant here rather than in a component — a date that silently becomes `Invalid Date`
 * renders as "NaN days ago", and a broken freshness reading is worse than none.
 */
export function parseRunAt(runAt: string | null | undefined): Date | null {
  if (!runAt) return null;
  const compact = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(runAt);
  const iso = compact
    ? `${compact[1]}-${compact[2]}-${compact[3]}T${compact[4]}:${compact[5]}:${compact[6]}Z`
    : runAt;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * A run's DAY, for a column that has room for a date and not for an instant.
 *
 * The obvious spelling — `run_at.slice(0, 10)` — is what two screens did, and on the basic
 * stamp the runner actually writes it takes ten characters off `20260801T120000Z` and renders
 * **`20260801T1`** under a heading that says "Dernière évaluation". Measured on the built
 * server in the per-agent breakdown; a date column showing a truncated timestamp reads as
 * corrupted data rather than as a formatting bug, which is the expensive kind of wrong.
 *
 * Parsing first is what makes the ten characters safe: an unparseable stamp yields the em dash
 * this cockpit uses for "no value", never a prefix of something the reader must decode.
 */
export function fmtRunDay(runAt: string | null | undefined): string {
  const at = parseRunAt(runAt);
  return at ? at.toISOString().slice(0, 10) : "—";
}

/**
 * CALENDAR days between a run and `now` — not 24-hour slices, and the difference is not
 * pedantic.
 *
 * The first draft divided the elapsed milliseconds by 86 400 000. A run from yesterday at 14:52,
 * read this morning, was 17 hours old — and the header announced "last run TODAY". True to the
 * arithmetic, false to the reader, which is this screen's entire failure mode. Calendar days in
 * UTC (the stamp's own zone) say "1 day ago", which is what happened.
 */
export function ageInDays(runAt: string | null | undefined, now: Date): number | null {
  const at = parseRunAt(runAt);
  if (!at) return null;
  const midnight = (d: Date) => Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  return Math.max(0, Math.round((midnight(now) - midnight(at)) / 86_400_000));
}

/**
 * Whether a run is stale — and note what this deliberately is NOT: a number of days.
 *
 * "Older than N days" would be an invented threshold, and this screen forbids those. A run is
 * stale when the CASE SET moved under it: its `catalogue_version` is no longer the catalogue's.
 * That is a measured fact, it needs no chosen constant, and it is the staleness that actually
 * matters — a verdict scored against cases that no longer exist. The age in days is displayed
 * beside it as a plain measurement, never as a gate.
 */
export function isStale(
  runVersion: string | null | undefined,
  currentVersion: string | null | undefined,
): boolean {
  if (!runVersion || !currentVersion) return false;
  return runVersion !== currentVersion;
}

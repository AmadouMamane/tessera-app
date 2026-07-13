/**
 * Server-only loader for the eval SWEEP — the screen's data model (spec §A1.4).
 *
 * What it replaces and why. `lib/eval.ts` read a single `latest.json`, and with three models
 * scored on one dataset "latest" means nothing: it cannot represent a sweep. Worse, the file it
 * actually resolved to was a THREE-CASE, ZERO-TOKEN run from 20 June, which the dashboard
 * rendered as "3/3 — 100%". Two failures in one: a run no model ever answered, published as a
 * perfect score, and three weeks of staleness passed off as current.
 *
 * A SWEEP is N runs on ONE catalogue version. That version is the *référentiel*, and it is a
 * property of the sweep, never a filter the reader chooses (criterion 2).
 *
 * Two sources, tried in order — the same contract `lib/eval.ts` documented:
 *   1. the live repo (`eval/reports/sweep/`, `eval/baselines/`, `eval/failures/`), so a fresh
 *      sweep shows up the moment it is written;
 *   2. the bundled snapshot (`data/eval/`), which is the ONLY source in the standalone image
 *      (no repo root there). `scripts/sync-eval-bundle.mjs` keeps it equal to the live one.
 *
 * The catalogue's version is COMPUTED here from the case files, exactly as the runner computes
 * it, and compared with what each run was stamped with. That is what lets the screen say "the
 * case set moved under this run" instead of quietly showing a verdict scored against cases that
 * no longer exist.
 */
import "server-only";

import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import { basename, dirname, join, resolve } from "node:path";

import {
  type EvalCase,
  EvalCaseSchema,
  NullControlBaselineSchema,
  type RunCost,
  type ScorecardDocument,
  ScorecardDocumentSchema,
  type ScorecardSummary,
} from "@/lib/api/schemas";
import { type Floor, type RunFacts, caseKey } from "@/lib/eval-score";

/** One run of the sweep: its facts and its score inputs, WITHOUT the 174 per-case results. */
export interface SweepRun extends RunFacts {
  /** Stable id, used in the URL. Derived from the filename, never from user input. */
  id: string;
  summary: ScorecardSummary;
  cost: RunCost | null;
  /** Wall-clock of the run, in ms — the honest half of "quality at what cost". */
  durationMs: number | null;
}

export interface Sweep {
  /** The référentiel the sweep is locked to — the catalogue version of its newest run. */
  catalogueVersion: string | null;
  /** Runs on THAT référentiel, newest first. */
  runs: SweepRun[];
  /**
   * Runs found alongside the sweep but scored on a DIFFERENT catalogue. Kept separate and
   * never merged in: their numbers are not comparable, and averaging them in would be exactly
   * the "delta without its référentiel" this screen exists to refuse.
   */
  offReferential: SweepRun[];
  /** The committed floor, restricted to nothing — read, never recomputed. */
  floor: Floor | null;
  floorTotals: { total: number; passed: number } | null;
  /** The catalogue AS IT STANDS TODAY (63 cases), and the version that follows from it. */
  catalogue: EvalCase[];
  currentCatalogueVersion: string | null;
  /** `{case_id: category}` — what Rule 3's zero-power derivation needs. */
  categoryOf: Record<string, string>;
  newestRunAt: string | null;
}

interface Sources {
  sweepDir: string;
  baselineFile: string;
  catalogue: { kind: "dir"; path: string } | { kind: "file"; path: string };
}

async function exists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

async function findRepoRoot(start: string): Promise<string | null> {
  let dir = resolve(start);
  for (;;) {
    if (await exists(join(dir, "pyproject.toml"))) return dir;
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

async function sources(): Promise<Sources | null> {
  const root = await findRepoRoot(process.cwd());
  if (root) {
    const sweepDir = join(root, "eval", "reports", "sweep");
    if (await exists(sweepDir)) {
      return {
        sweepDir,
        baselineFile: join(root, "eval", "baselines", "null-control.json"),
        catalogue: { kind: "dir", path: join(root, "eval", "failures") },
      };
    }
  }
  const bundle = join(process.cwd(), "data", "eval");
  if (await exists(join(bundle, "sweep"))) {
    return {
      sweepDir: join(bundle, "sweep"),
      baselineFile: join(bundle, "null-control.json"),
      catalogue: { kind: "file", path: join(bundle, "catalogue.json") },
    };
  }
  return null;
}

/**
 * The catalogue's version — the TypeScript mirror of `eval/runner.py::_catalogue_version`
 * (`{count}-{sha256(sorted ids joined by \n)[:8]}`).
 *
 * It exists so the screen can ask a question no stamp can answer on its own: *is the case set
 * still the one this run was scored against?* Both sides sort ASCII ids, so both sides agree.
 */
export function catalogueVersionOf(cases: ReadonlyArray<{ id: string }>): string {
  const ids = cases.map((c) => c.id).sort();
  const digest = createHash("sha256").update(ids.join("\n")).digest("hex").slice(0, 8);
  return `${ids.length}-${digest}`;
}

export async function loadCatalogue(): Promise<EvalCase[]> {
  const src = await sources();
  if (!src) return [];
  try {
    if (src.catalogue.kind === "file") {
      const raw = JSON.parse(await readFile(src.catalogue.path, "utf-8"));
      return EvalCaseSchema.array().parse(raw);
    }
    const files = (await readdir(src.catalogue.path))
      .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
      .sort();
    const cases: EvalCase[] = [];
    for (const file of files) {
      const raw = JSON.parse(await readFile(join(src.catalogue.path, file), "utf-8"));
      cases.push(EvalCaseSchema.parse(raw));
    }
    return cases;
  } catch {
    // A malformed catalogue is honest-empty, never a partial one: the screen would then show
    // "no case covers this capability" about cases that exist.
    return [];
  }
}

async function loadFloor(
  file: string,
): Promise<{ floor: Floor; totals: { total: number; passed: number } } | null> {
  try {
    const doc = NullControlBaselineSchema.parse(JSON.parse(await readFile(file, "utf-8")));
    return {
      floor: {
        catalogueVersion: doc.catalogue_version ?? null,
        verdicts: doc.verdicts,
      },
      totals: doc.totals,
    };
  } catch {
    return null;
  }
}

function toSweepRun(id: string, doc: ScorecardDocument): SweepRun {
  const verdicts: Record<string, boolean> = {};
  let durationMs = 0;
  let anyDuration = false;
  for (const r of doc.results) {
    verdicts[caseKey(r.case_id, r.language)] = r.passed;
    if (r.duration_ms !== null) {
      durationMs += r.duration_ms;
      anyDuration = true;
    }
  }
  return {
    id,
    model: doc.model ?? null,
    runAt: doc.run_at ?? null,
    catalogueVersion: doc.catalogue_version ?? null,
    outputTokens: doc.cost?.output_tokens ?? 0,
    verdicts,
    summary: doc.summary,
    cost: doc.cost ?? null,
    durationMs: anyDuration ? durationMs : null,
  };
}

/** Timestamped filenames (`20260712T131902Z.json`) and `latest.json` are aliases of a run. */
function isAliasFilename(file: string): boolean {
  const stem = basename(file, ".json");
  return stem === "latest" || /^\d{8}T\d{6}Z$/.test(stem);
}

/**
 * Read the sweep.
 *
 * The directory holds each run more than once — a timestamped copy, a model-named copy, and a
 * `latest.json`. They are ALIASES, not runs: counting them would report a three-model sweep as
 * seven. Runs are therefore deduplicated by `run_at`, and the model-named file wins because its
 * name is the only one an operator can read.
 */
export async function loadSweep(): Promise<Sweep | null> {
  const src = await sources();
  if (!src) return null;

  const files = (await readdir(src.sweepDir)).filter((f) => f.endsWith(".json"));
  const byRunAt = new Map<string, { id: string; doc: ScorecardDocument }>();
  for (const file of files.sort()) {
    let doc: ScorecardDocument;
    try {
      doc = ScorecardDocumentSchema.parse(
        JSON.parse(await readFile(join(src.sweepDir, file), "utf-8")),
      );
    } catch {
      continue; // a malformed report is not a run
    }
    const key = doc.run_at ?? file;
    const existing = byRunAt.get(key);
    if (!existing || (isAliasFilename(existing.id) && !isAliasFilename(file))) {
      byRunAt.set(key, { id: basename(file, ".json"), doc });
    }
  }

  const all = [...byRunAt.values()]
    .map(({ id, doc }) => toSweepRun(id, doc))
    .sort((a, b) => (b.runAt ?? "").localeCompare(a.runAt ?? ""));

  // The sweep's référentiel is the newest run's. Everything else in the directory that was
  // scored elsewhere is held apart rather than averaged in.
  const catalogueVersion = all[0]?.catalogueVersion ?? null;
  const runs = all.filter((r) => r.catalogueVersion === catalogueVersion);
  const offReferential = all.filter((r) => r.catalogueVersion !== catalogueVersion);

  const floorDoc = await loadFloor(src.baselineFile);
  const catalogue = await loadCatalogue();

  return {
    catalogueVersion,
    runs,
    offReferential,
    floor: floorDoc?.floor ?? null,
    floorTotals: floorDoc?.totals ?? null,
    catalogue,
    currentCatalogueVersion: catalogue.length ? catalogueVersionOf(catalogue) : null,
    categoryOf: Object.fromEntries(catalogue.map((c) => [c.id, c.category])),
    newestRunAt: all[0]?.runAt ?? null,
  };
}

/**
 * The full report of ONE run — the 174 per-case results the detail view needs.
 *
 * `id` arrives from the query string, so it is resolved against the ids the sweep actually
 * holds instead of being joined onto a path. A `?run=../../../etc/passwd` reaches `readFile`
 * otherwise, and a dashboard is not a place to discover that.
 */
export async function loadSweepRun(
  id: string | undefined,
  sweep: Sweep,
): Promise<ScorecardDocument | null> {
  const src = await sources();
  if (!src) return null;
  const known = [...sweep.runs, ...sweep.offReferential].find((r) => r.id === id);
  if (!known) return null;
  try {
    const raw = await readFile(join(src.sweepDir, `${known.id}.json`), "utf-8");
    return ScorecardDocumentSchema.parse(JSON.parse(raw));
  } catch {
    return null;
  }
}

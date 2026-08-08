/**
 * Server-only loader for the eval SWEEP — now a READER of the API, not of the disk.
 *
 * What changed, and why it is not a refactor. This module used to walk the filesystem: the
 * repository's own `eval/reports/sweep/` when a `pyproject.toml` sat above the working
 * directory, and a bundle baked into the image otherwise. Every sibling block of the SAME
 * page — the SLO ribbon, the signal registry, the per-agent breakdown — read the FastAPI
 * backend. One screen, two media, and they do not fail alike: `eval/reports` is bind-mounted
 * into the agent container and moves the instant a file changes, while the bundle freezes at
 * the commit that built the image. A re-grade that landed moved half the page and left the
 * other half telling last month's story (ADR 0051's chimera).
 *
 * Two more things followed from the split, and they are the reason this is worth doing:
 *
 *  - the backend could not SEE the sweep at all (`iter_report_files` reads `local/` and
 *    `seed/`), so the two views of Qualité IA were not merely two instants — they were two
 *    disjoint populations of runs, catalogue-wide here and per-agent there;
 *  - the provenance never crossed the wire. The committed runs were sampled on 12 July and
 *    re-judged on 5 August, and `ScorecardDocumentSchema` declared neither `regraded_at` nor
 *    the grader's sha, so zod stripped them in silence and the header could only say "26 days
 *    ago" — true of the sampling, false of every verdict on screen.
 *
 * So the sweep has ONE address (`/observability/eval-sweep`), and its provenance is the
 * payload's point. The catalogue-version arithmetic that used to be mirrored here in
 * TypeScript is gone with it: it now lives once, on the Python side, pinned by
 * `tests/unit/test_eval_sweep_api.py` to the stamp the committed reports actually carry.
 * Two implementations of one hash are two answers waiting to disagree.
 *
 * Every read returns `null` on failure so a caller renders an honest empty state — never a
 * fixture, and never a zero that would read as a measurement.
 */
import "server-only";

import { cache } from "react";

import {
  type CataloguePower,
  CataloguePowerSchema,
  type EvalCase,
  EvalSweepPayloadSchema,
  type RunCost,
  type ScorecardDocument,
  ScorecardDocumentSchema,
  type ScorecardSummary,
} from "@/lib/api/schemas";
import type { Floor, RunFacts } from "@/lib/eval-score";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

/** One run of the sweep: its facts and its score inputs, WITHOUT the 174 per-case results. */
export interface SweepRun extends RunFacts {
  /** Stable id, used in the URL. Derived from the report's filename, never from user input. */
  id: string;
  summary: ScorecardSummary;
  cost: RunCost | null;
  /** Wall-clock of the run, in ms — the honest half of "quality at what cost". */
  durationMs: number | null;
  /**
   * When these verdicts were last JUDGED, as opposed to when the model answered (`runAt`).
   * A re-grade re-judges recorded responses under moved criteria: it changes the pass rate
   * without changing `runAt`, so a screen showing only `runAt` cannot say the numbers moved.
   */
  regradedAt: string | null;
  regradeNote: string | null;
  /** The ruler. Mutually exclusive with {@link graderShaPartial} by construction. */
  graderSha: string | null;
  /** A ruler that judged MOST of the run — it travels with {@link graderBlindRuns}. */
  graderShaPartial: string | null;
  /**
   * The `case|language` runs whose verdict was CARRIED, not re-derived — a criterion the
   * recording cannot answer (max_confidence, must_cite_source). Non-empty means the sha above
   * is the rule that was applied, not a claim that it judged everything.
   */
  graderBlindRuns: string[];
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
  /** The ruler the floor itself was measured under — the other half of any comparison. */
  floorGraderSha: string | null;
  /** The catalogue AS IT STANDS TODAY (63 cases), and the version that follows from it. */
  catalogue: EvalCase[];
  currentCatalogueVersion: string | null;
  /** `{case_id: category}` — what Rule 3's zero-power derivation needs. */
  categoryOf: Record<string, string>;
  /**
   * The fields a case is ALLOWED to declare (`eval/failures/_schema.json`, `additionalProperties:
   * false`). The coverage map needs it: whether a case can even NAME a capability is a property of
   * the schema, and the answer decides whether that map can be drawn at all or only its absence
   * can be stated.
   */
  caseSchemaFields: string[];
  newestRunAt: string | null;
  /** The most recent re-grade across the sweep — the instant its verdicts were last decided. */
  newestRegradedAt: string | null;
}

/**
 * What the catalogue measures — or WHY that cannot be said.
 *
 * The classification is pinned to the case set it was measured on. If the catalogue has moved
 * since, every count in it describes runs that no longer exist, so this returns a REFUSAL
 * rather than numbers: unusable is not the same as zero (ADR 0026). The screen prints the
 * reason instead of a hole, because a tile that renders nothing is indistinguishable from a
 * catalogue with no discriminating power at all — and those are opposite facts.
 *
 * Four states, and `unreadable` is the one that was missing. "Nobody has measured this" and "it
 * was measured and I cannot read the artefact" are **different facts**, and both used to arrive as
 * `not-measured`. A schema change on the Python side would then have silently reclassified a live
 * measurement as an absent one, and the tile would have said "not measured yet" about a file
 * sitting right there with 174 verdicts in it. It says what it cannot read now.
 */
export type CataloguePowerState =
  | { kind: "measured"; power: CataloguePower }
  | { kind: "not-measured" }
  | { kind: "unreadable"; reason: string }
  | { kind: "off-referential"; measuredOn: string; current: string };

/**
 * Why the sweep is not on screen. A BLIND read and a MEASURED absence are different facts.
 *
 * Four causes used to collapse into one `null`: the backend could not be reached, it answered
 * with an error, its payload no longer matched the contract, or it answered perfectly well and
 * said there is nothing readable under `eval/reports/sweep/`. Only the last is a fact about the
 * evaluation; the first three are facts about the READ, and an operator who is told "no readable
 * sweep" goes and looks at a directory that may be full.
 *
 * This is the same fault the ClickHouse adapter carried (an empty list asserted "nothing was
 * emitted" over a failed query), stated once more in ADR 0026's terms: a witness that cannot see
 * may report a blind spot, never a result.
 */
export type SweepUnavailable =
  /** The request never completed — no backend, DNS, TLS, abort. Nothing was measured. */
  | { kind: "unreachable"; detail: string }
  /** The backend answered, and refused. Its status is the operator's first clue. */
  | { kind: "refused"; status: number }
  /** It answered, and the payload is not the shape this build expects — the contract drifted. */
  | { kind: "contract"; detail: string }
  /** It answered, it was understood, and it says there is nothing to show. A real measurement. */
  | { kind: "absent" };

type SweepFetch = { ok: true; payload: SweepPayloadShape } | { ok: false; why: SweepUnavailable };

type SweepPayloadShape = ReturnType<typeof EvalSweepPayloadSchema.parse>;

/**
 * The read itself, UNCACHED and exported — so the four-way classification can be tested.
 *
 * It sits outside `cache()` deliberately. React's `cache` memoises per request scope, and a test
 * driving four different backend behaviours through one memoised function would get the first
 * answer four times: the classification would look correct while never running. A witness that
 * cannot vary its input is not testing the branch it names.
 */
export async function readSweep(url: string): Promise<SweepFetch> {
  let res: Response;
  try {
    res = await fetch(url, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
  } catch (error) {
    return { ok: false, why: { kind: "unreachable", detail: String(error) } };
  }
  if (!res.ok) return { ok: false, why: { kind: "refused", status: res.status } };
  try {
    const parsed = EvalSweepPayloadSchema.parse(await res.json());
    // `available: false` is the backend's own verdict, reached after looking. Keep it distinct
    // from the three failures above: it is the only one that says something about the data.
    return parsed.available
      ? { ok: true, payload: parsed }
      : { ok: false, why: { kind: "absent" } };
  } catch (error) {
    return { ok: false, why: { kind: "contract", detail: String(error) } };
  }
}

/**
 * The one backend read, wrapped in React `cache()`.
 *
 * The evaluations view asks for the sweep more than once in a single render tree (the score
 * cards, the matrix, the power tile), and the key is the URL STRING, so the dedup is exact:
 * request-scoped, never across renders, so freshness is byte-identical to a plain `no-store`.
 * The empty states ask the SAME cached call for their reason, so naming the cause costs no
 * second request and cannot describe a different attempt from the one that failed.
 */
const fetchSweep = cache(readSweep);

const fetchSweepPayload = async (url: string): Promise<SweepPayloadShape | null> => {
  const result = await fetchSweep(url);
  return result.ok ? result.payload : null;
};

type SweepPayload = SweepPayloadShape;
type SweepRunPayload = SweepPayload["runs"][number];

function toRun(run: SweepRunPayload): SweepRun {
  return {
    id: run.id,
    model: run.model,
    runAt: run.run_at,
    catalogueVersion: run.catalogue_version,
    outputTokens: run.output_tokens,
    verdicts: run.verdicts,
    summary: run.summary,
    cost: run.cost,
    durationMs: run.duration_ms,
    regradedAt: run.regraded_at,
    regradeNote: run.regrade_note,
    graderSha: run.grader_criteria_sha,
    graderShaPartial: run.grader_criteria_sha_partial,
    graderBlindRuns: run.grader_blind_runs,
  };
}

/** Shape the payload into the screen's model. Pure, so the mapping is testable without a server. */
export function toSweep(payload: SweepPayload): Sweep {
  const runs = payload.runs.map(toRun);
  const regrades = [...runs, ...payload.off_referential.map(toRun)]
    .map((r) => r.regradedAt)
    .filter((at): at is string => at !== null)
    .sort();

  return {
    catalogueVersion: payload.catalogue_version,
    runs,
    offReferential: payload.off_referential.map(toRun),
    floor: payload.floor
      ? {
          catalogueVersion: payload.floor.catalogue_version ?? null,
          verdicts: payload.floor.verdicts,
        }
      : null,
    floorTotals: payload.floor?.totals ?? null,
    floorGraderSha: payload.floor?.grader_criteria_sha ?? null,
    catalogue: payload.catalogue,
    currentCatalogueVersion: payload.current_catalogue_version,
    categoryOf: Object.fromEntries(payload.catalogue.map((c) => [c.id, c.category])),
    caseSchemaFields: payload.case_schema_fields,
    newestRunAt: payload.newest_run_at,
    newestRegradedAt: regrades.at(-1) ?? null,
  };
}

/** Read the sweep. `null` when the backend cannot answer — never a fabricated empty sweep. */
export async function loadSweep(): Promise<Sweep | null> {
  const payload = await fetchSweepPayload(`${backendUrl()}/observability/eval-sweep`);
  return payload ? toSweep(payload) : null;
}

/**
 * WHY there is no sweep, for the screen that has to say so. `null` when there is one.
 *
 * Shares `loadSweep`'s cached call, so the reason describes the very attempt that failed rather
 * than a second, possibly luckier one. Every empty state on this view reads it: the alternative
 * is one sentence for four causes, which is how the copy came to name a fallback the code had
 * stopped opening months earlier.
 */
export async function sweepUnavailableReason(): Promise<SweepUnavailable | null> {
  const result = await fetchSweep(`${backendUrl()}/observability/eval-sweep`);
  return result.ok ? null : result.why;
}

/** The catalogue as it stands today, from the same one read. */
export async function loadCatalogue(): Promise<EvalCase[]> {
  const payload = await fetchSweepPayload(`${backendUrl()}/observability/eval-sweep`);
  return payload?.catalogue ?? [];
}

/**
 * What the catalogue MEASURES, derived from the SAME payload the sweep came from.
 *
 * It used to be a second read of a second artefact; deriving both from one response is what
 * makes it impossible for the tile and the runs beside it to describe two different instants.
 */
export async function loadCataloguePower(
  currentCatalogueVersion: string,
): Promise<CataloguePowerState> {
  const payload = await fetchSweepPayload(`${backendUrl()}/observability/eval-sweep`);
  if (!payload) return { kind: "not-measured" };
  if (payload.power_error) return { kind: "unreadable", reason: payload.power_error };
  if (payload.power === null || payload.power === undefined) return { kind: "not-measured" };

  const parsed = CataloguePowerSchema.safeParse(payload.power);
  if (!parsed.success) {
    // The artefact EXISTS and this code cannot read it. That is a blind spot, not an absence,
    // and reporting it as "not measured yet" would be a witness describing its own ignorance
    // as a property of the world.
    return {
      kind: "unreadable",
      reason: parsed.error.issues
        .slice(0, 3)
        .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
        .join("; "),
    };
  }

  const power = parsed.data;
  if (power.catalogue_version !== currentCatalogueVersion) {
    return {
      kind: "off-referential",
      measuredOn: power.catalogue_version,
      current: currentCatalogueVersion,
    };
  }
  return { kind: "measured", power };
}

/**
 * The full report of ONE run — the 174 per-case results the detail view needs.
 *
 * `id` arrives from the query string, so it is resolved against the ids the sweep actually
 * holds BEFORE any call is made, and the backend resolves it a second time against the
 * directory's own stems. A dashboard is not a place to discover a path traversal, and one
 * check on each side of the wire is the cheap way never to.
 *
 * This carries the models' real responses, so it goes to a bearer-gated route that the front's
 * public `/api` proxy deliberately does not relay (`/eval/…`, not `/observability/…`). The
 * operator gate itself stays where it was: the calling server component checks the role.
 */
export async function loadSweepRun(
  id: string | undefined,
  sweep: Sweep,
): Promise<ScorecardDocument | null> {
  const known = [...sweep.runs, ...sweep.offReferential].find((r) => r.id === id);
  if (!known) return null;
  try {
    const res = await fetch(
      `${backendUrl()}/eval/sweep-run?run_id=${encodeURIComponent(known.id)}`,
      { cache: "no-store", headers: backendHeaders({ Accept: "application/json" }) },
    );
    if (!res.ok) return null;
    return ScorecardDocumentSchema.parse(await res.json());
  } catch {
    return null;
  }
}

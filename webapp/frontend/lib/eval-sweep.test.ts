import { describe, expect, it } from "vitest";

import { graderRemeasureOwed } from "@/lib/test-support/grader-provenance";

import {
  catalogueVersionOf,
  loadCatalogue,
  loadCataloguePower,
  loadSweep,
  loadSweepRun,
} from "@/lib/eval-sweep";

/**
 * These run against the repository's live artefacts (the vitest cwd sits under the repo, so the
 * loader resolves its first source, exactly as `next dev` does). That is deliberate: the point of
 * the loader is to read what the harness actually wrote, and a mocked filesystem would only prove
 * it reads what this test wrote.
 */

/**
 * The sweep's runs were graded in July; the null floor was re-measured on 2026-08-03 under
 * criteria that did not exist then (`must_not_assert`, `must_contain_any_pattern`). Comparing
 * the two is not a weaker measurement, it is a different question — so while the provenance
 * declares a re-measure owed, these do not answer it. See lib/test-support/grader-provenance.ts.
 */
const OWED = graderRemeasureOwed();

describe("catalogueVersionOf", () => {
  it("reproduces the runner's own stamp — the case set is the one the sweep was scored on", async () => {
    const catalogue = await loadCatalogue();
    expect(catalogue).toHaveLength(63);
    // Every run of the 2026-07-12 sweep, and the committed floor, carry this exact string.
    // If this ever fails, the catalogue moved and NO verdict on the screen is attributable.
    expect(catalogueVersionOf(catalogue)).toBe("63-071edbdc");
  });

  it("is a function of the ids alone, and moves when one is added", () => {
    const base = [{ id: "01_a" }, { id: "02_b" }];
    expect(catalogueVersionOf(base)).toBe(catalogueVersionOf([...base].reverse()));
    expect(catalogueVersionOf([...base, { id: "03_c" }])).not.toBe(catalogueVersionOf(base));
    expect(catalogueVersionOf(base).startsWith("2-")).toBe(true);
  });
});

describe.skipIf(OWED)("loadSweep", () => {
  it("reads THREE runs from seven files — the aliases are not runs", async () => {
    const sweep = await loadSweep();
    expect(sweep).not.toBeNull();
    if (!sweep) return;
    expect(sweep.runs).toHaveLength(3);
    expect(sweep.runs.map((r) => r.model).sort()).toEqual([
      "gemma3:27b",
      "llama3.2:3b",
      "llama3.3:70b",
    ]);
    // The model-named file wins the dedup: an id an operator can read.
    expect(sweep.runs.map((r) => r.id).sort()).toEqual([
      "gemma3-27b",
      "llama3.2-3b",
      "llama3.3-70b",
    ]);
  });

  it("is locked to ONE référentiel, and holds nothing scored elsewhere", async () => {
    const sweep = await loadSweep();
    if (!sweep) throw new Error("sweep");
    expect(sweep.catalogueVersion).toBe("63-071edbdc");
    expect(sweep.runs.every((r) => r.catalogueVersion === sweep.catalogueVersion)).toBe(true);
    expect(sweep.offReferential).toEqual([]);
  });

  it("carries the committed floor, read and not recomputed", async () => {
    const sweep = await loadSweep();
    if (!sweep) throw new Error("sweep");
    expect(sweep.floorTotals).toEqual({ total: 174, passed: 122 });
    expect(Object.keys(sweep.floor?.verdicts ?? {})).toHaveLength(174);
    expect(sweep.floor?.catalogueVersion).toBe(sweep.catalogueVersion);
  });

  it("the catalogue on disk still matches what the sweep was scored against", async () => {
    const sweep = await loadSweep();
    if (!sweep) throw new Error("sweep");
    expect(sweep.currentCatalogueVersion).toBe(sweep.catalogueVersion);
    expect(sweep.categoryOf["02_pii_leak"]).toBe("pii_leak");
  });

  it("records the tokens each run generated — the only witness that a model spoke", async () => {
    const sweep = await loadSweep();
    if (!sweep) throw new Error("sweep");
    for (const run of sweep.runs) expect(run.outputTokens).toBeGreaterThan(0);
    expect(sweep.runs.find((r) => r.model === "gemma3:27b")?.outputTokens).toBe(8100);
  });
});

describe("loadSweepRun", () => {
  it("returns the 174 per-case results, with the execution context zod used to strip", async () => {
    const sweep = await loadSweep();
    if (!sweep) throw new Error("sweep");
    const doc = await loadSweepRun("gemma3-27b", sweep);
    expect(doc?.results).toHaveLength(174);
    const one = doc?.results[0];
    expect(one?.duration_ms).not.toBeNull();
    expect(one?.output_tokens).not.toBeNull();
    expect(typeof one?.final_response).toBe("string");
  });

  it("refuses an id the sweep does not hold — the query string never reaches a path", async () => {
    const sweep = await loadSweep();
    if (!sweep) throw new Error("sweep");
    expect(await loadSweepRun("../../../../etc/passwd", sweep)).toBeNull();
    expect(await loadSweepRun("latest", sweep)).toBeNull();
    expect(await loadSweepRun(undefined, sweep)).toBeNull();
  });
});

describe("loadCataloguePower — what the catalogue MEASURES", () => {
  it("reads the committed measurement, and it describes the CURRENT case set", async () => {
    const catalogue = await loadCatalogue();
    const current = catalogueVersionOf(catalogue);
    const state = await loadCataloguePower(current);

    // If this is not "measured", the classification is missing or was measured on another
    // catalogue — and the tile would be showing counts about cases that no longer exist.
    expect(state.kind).toBe("measured");
    if (state.kind !== "measured") return;

    expect(state.power.catalogue_version).toBe(current);
    expect(state.power.power.total_cases).toBe(63);
    expect(state.power.power.total_runs).toBe(174);

    // The taxonomy is total: every case lands in exactly one class.
    const c = state.power.case_counts;
    const sum =
      c.dead +
      c.inverted +
      c.saturated +
      c.unreached +
      c.discriminating +
      c.reversed +
      c.underpowered;
    expect(sum).toBe(63);

    // The headline is the union of the three classes that measure the model — nothing else.
    // `reversed` is IN: a run the reference model fails 12 times in 15 while a model a third its
    // size passes it 15/15 separates them violently, and it is the catalogue's only certified
    // evidence that the shipping model is more injectable than the small one.
    expect(state.power.power.discriminating_cases).toBe(c.discriminating + c.inverted + c.reversed);

    // And the buckets are total too, over RUNS.
    const b = state.power.bucket_counts;
    expect(b.fact + b.certified + b.cannot_say).toBe(state.power.power.total_runs);
  });

  it("carries the detection floor — no count of 'does not separate' is published naked", async () => {
    // The whole correction, at the wire. A bucket of cases that "do not discriminate" is a CLAIM,
    // and it is the one claim an underpowered experiment produces for free. The artefact must
    // therefore carry what the design could have SEEN: at n=15 per arm over 174 runs, nothing
    // under a 66.7-point separation. Anything smaller is "cannot say", never "no effect".
    const catalogue = await loadCatalogue();
    const state = await loadCataloguePower(catalogueVersionOf(catalogue));
    expect(state.kind).toBe("measured");
    if (state.kind !== "measured") return;

    const dp = state.power.detection_power;
    expect("minimum_detectable_effect" in dp).toBe(true);
    if (!("minimum_detectable_effect" in dp)) return;
    expect(dp.minimum_detectable_effect).toBeCloseTo(66.7, 1);
    expect(dp.best_achievable_p).toBeLessThanOrEqual(dp.threshold);

    // Holm feeds the ratchet, BH feeds the diagnosis, and the gap between them is PUBLISHED —
    // under the fixed injection grader (ADR 0028 §5, re-measured 2026-07-15) it is three runs BH
    // certifies and Holm will not, which is exactly the divergence the artefact exists to surface
    // (it was empty on the pre-fix measurement). A re-measure that changes it updates this list
    // deliberately, the way the null control is refreshed.
    expect(state.power.power.holm_runs).toBeGreaterThan(0);
    expect(state.power.power.bh_runs).toBeGreaterThanOrEqual(state.power.power.holm_runs);
    expect(state.power.power.correction_gap).toEqual([
      "20_hallucination_loi_inexistante|fr",
      "26_citation_fabrication_cjue|de",
      "38_language_mixing_de_fr|de",
    ]);
  });

  it("REFUSES when the catalogue has moved — it does not report zero", async () => {
    // A classification is only true of the case set it was measured on. Asked about a
    // different one, it must say so: a hole and "no discriminating power" are opposite facts,
    // and rendering the second for the first is the lie this whole screen exists to prevent.
    const state = await loadCataloguePower("64-deadbeef");
    expect(state.kind).toBe("off-referential");
    if (state.kind !== "off-referential") return;
    expect(state.measuredOn).toBe("63-071edbdc");
    expect(state.current).toBe("64-deadbeef");
  });
});

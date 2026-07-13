import { describe, expect, it } from "vitest";

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

describe("loadSweep", () => {
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
      c.dead + c.inverted + c.discriminating + c.reversed + c.undecided + c.non_discriminating;
    expect(sum).toBe(63);

    // The headline is the union of the two classes that measure the model — nothing else.
    expect(state.power.power.discriminating_cases).toBe(c.discriminating + c.inverted);
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

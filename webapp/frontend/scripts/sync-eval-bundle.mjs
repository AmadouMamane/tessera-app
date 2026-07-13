// Regenerate the bundled eval fallback (`webapp/frontend/data/eval/`) from the LIVE artefacts
// at build time.
//
// Why this exists: `lib/eval-sweep.ts` prefers the repository's own files, but the deployed
// standalone image has no repo root, so it falls back to this bundle. Without a regeneration
// step the bundle drifts — and it HAD drifted: the committed fallback carried a three-case,
// zero-token run from 20 June, which the cockpit rendered as "3/3 — 100%".
//
// What it bundles, and why all three are needed:
//   - `eval/reports/sweep/`      the runs. A sweep is N runs on ONE case set; "latest" cannot
//                                represent one, so the whole sweep travels, not a single file.
//   - `eval/baselines/null-control.json`  the FLOOR (122/174 with no model at all). Without it
//                                the image cannot decompose a score, and an undecomposed score
//                                is the one thing this screen may not print.
//   - `eval/failures/*.json`     the catalogue, assembled into one array. It carries the prompts,
//                                the pass criteria and the source citations — the evidence behind
//                                every verdict, and the reason the bench is not "invented".
//
// It is a no-op when the repo is absent (inside the image build, where the committed bundle is
// used as-is), a no-op when there is no sweep to sync from (a bundle is never deleted because a
// checkout happens to have no reports), and it never fails the build.

import { copyFile, mkdir, readFile, readdir, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const log = (message) => {
  // biome-ignore lint/suspicious/noConsole: build-script status output
  console.log(`[sync-eval-bundle] ${message}`);
};

async function findRepoRoot(start) {
  let dir = resolve(start);
  for (;;) {
    try {
      await stat(join(dir, "pyproject.toml"));
      return dir;
    } catch {
      // keep walking up
    }
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

/** Drop every `.json` under `dir` that the new bundle does not claim. */
async function pruneStale(dir, keep) {
  for (const existing of await readdir(dir)) {
    if (existing.endsWith(".json") && !keep.has(existing)) {
      await rm(join(dir, existing));
      log(`dropped stale ${existing}`);
    }
  }
}

async function main() {
  const here = dirname(fileURLToPath(import.meta.url));
  const root = await findRepoRoot(here);
  if (!root) {
    log("no repo root — keeping the committed bundle.");
    return;
  }

  const sweepSrc = join(root, "eval", "reports", "sweep");
  if (!(await exists(sweepSrc))) {
    // "Nothing to sync from" is NOT "the bundle is stale". Falling through would delete the
    // deployed cockpit's only data source.
    log("no eval/reports/sweep — keeping the committed bundle.");
    return;
  }

  const dest = join(root, "webapp", "frontend", "data", "eval");
  const sweepDest = join(dest, "sweep");
  await mkdir(sweepDest, { recursive: true });

  // 1. The sweep's runs, verbatim. The loader deduplicates the aliases (a run appears as a
  //    timestamped file, a model-named file and `latest.json`), so no selection happens here.
  const runs = (await readdir(sweepSrc)).filter((f) => f.endsWith(".json"));
  for (const file of runs) await copyFile(join(sweepSrc, file), join(sweepDest, file));
  await pruneStale(sweepDest, new Set(runs));

  // 2. The committed floor. The image reads it, never recomputes it.
  const floorSrc = join(root, "eval", "baselines", "null-control.json");
  const bundled = new Set();
  if (await exists(floorSrc)) {
    await copyFile(floorSrc, join(dest, "null-control.json"));
    bundled.add("null-control.json");
  } else {
    log("WARNING: no committed null baseline — the image will not be able to decompose a score.");
  }

  // 3. The catalogue, assembled. One file rather than 63: the image reads it whole, every time.
  const casesDir = join(root, "eval", "failures");
  if (await exists(casesDir)) {
    const files = (await readdir(casesDir))
      .filter((f) => f.endsWith(".json") && !f.startsWith("_"))
      .sort();
    const cases = [];
    for (const file of files) {
      cases.push(JSON.parse(await readFile(join(casesDir, file), "utf-8")));
    }
    await writeFile(join(dest, "catalogue.json"), `${JSON.stringify(cases, null, 2)}\n`);
    bundled.add("catalogue.json");
    log(`assembled ${cases.length} cases into catalogue.json`);

    // 4. The case SCHEMA. The coverage card reads it to answer a question the catalogue cannot:
    //    can a case even NAME a capability it covers? (`additionalProperties: false` and no such
    //    field ⇒ the map is not empty, it is inexpressible.) Bundled so the image can say so too.
    const schema = join(casesDir, "_schema.json");
    if (await exists(schema)) {
      await copyFile(schema, join(dest, "case-schema.json"));
      bundled.add("case-schema.json");
    }
  }

  // The `latest*.json` files the old single-run loader read are dead weight now, and dead weight
  // that still parses is how a three-week-old run gets published as today's.
  await pruneStale(dest, bundled);

  log(`refreshed ${runs.length} sweep file(s), the floor and the catalogue.`);
}

main().catch((err) => {
  // Never break the build over the fallback bundle.
  console.warn(`[sync-eval-bundle] skipped: ${err?.message ?? err}`);
});

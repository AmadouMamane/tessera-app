// Regenerate the bundled eval scorecard fallback (`webapp/frontend/data/eval/`)
// from the LIVE run reports (`eval/reports/`) at build time.
//
// Why this exists: `lib/eval.ts` prefers the live repo reports, but the deployed
// standalone image has no repo root, so it falls back to this bundle. Without a
// regeneration step the bundle drifts (it was a hand-curated snapshot), and the
// deployed cockpit would show STALE verdicts that disagree with the launcher and
// the live reports. This script keeps the fallback equal to the latest run.
//
// It is a no-op when `eval/reports/` is absent (e.g. inside the standalone image
// build, where the committed bundle is used as-is) and never fails the build.

import { copyFile, mkdir, readFile, readdir, rm, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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

async function main() {
  const here = dirname(fileURLToPath(import.meta.url));
  const root = await findRepoRoot(here);
  if (!root) {
    // biome-ignore lint/suspicious/noConsole: build-script status output
    console.log("[sync-eval-bundle] no repo root — keeping committed bundle.");
    return;
  }
  const src = join(root, "eval", "reports");
  const dest = join(root, "webapp", "frontend", "data", "eval");
  try {
    await stat(src);
  } catch {
    // biome-ignore lint/suspicious/noConsole: build-script status output
    console.log("[sync-eval-bundle] no eval/reports — keeping committed bundle.");
    return;
  }

  const files = await readdir(src);
  const keep = new Set();
  // Global latest scorecard.
  if (files.includes("latest.json")) keep.add("latest.json");
  // Per-agent latests + the timestamped archive each one points at, so the
  // deployed history view shows the agent's real reference run.
  for (const f of files.filter((n) => /^latest_.+\.json$/.test(n))) {
    keep.add(f);
    try {
      const doc = JSON.parse(await readFile(join(src, f), "utf-8"));
      const runAt = typeof doc.run_at === "string" ? doc.run_at : null;
      const agent = typeof doc.agent_id === "string" ? doc.agent_id : null;
      if (runAt) {
        for (const g of files) {
          if (g.startsWith(runAt) && (!agent || g.includes(agent))) keep.add(g);
        }
      }
    } catch {
      // skip malformed latest_*.json
    }
  }

  await mkdir(dest, { recursive: true });
  // Drop stale bundle files no longer in the keep set.
  for (const existing of await readdir(dest)) {
    if (existing.endsWith(".json") && !keep.has(existing)) {
      await rm(join(dest, existing));
    }
  }
  for (const k of keep) {
    await copyFile(join(src, k), join(dest, k));
  }
  // biome-ignore lint/suspicious/noConsole: build-script status output
  console.log(`[sync-eval-bundle] refreshed ${keep.size} file(s) from the latest run.`);
}

main().catch((err) => {
  // Never break the build over the fallback bundle.
  console.warn(`[sync-eval-bundle] skipped: ${err?.message ?? err}`);
});

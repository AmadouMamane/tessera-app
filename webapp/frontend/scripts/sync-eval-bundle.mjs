// The bundled eval snapshot (`webapp/frontend/data/eval/`) is a DERIVED artefact with ONE
// author: `scripts/build_eval_bundle.py` at the repo root, held to the repo by the ratchet
// `tests/unit/test_eval_bundle_is_derived.py`.
//
// This hook used to be a second author. It assembled the bundle itself, from its own file
// list, and the two lists drifted the way two originals always do: this one never learned
// `discrimination.json`, so its prune step deleted the catalogue-power measurement from the
// bundle on every local `pnpm build` — recreating at build time the exact incident the Python
// builder exists to prevent (measured 2026-08-05 on the serving container: a tile answering
// "not measured" over a measurement that had been run).
//
// So it no longer knows any file name. It finds the one author and runs it:
//   - no repo root (the Docker image build copies `webapp/frontend/` alone, so there is no
//     `pyproject.toml` above) → no-op, the committed bundle is used as-is;
//   - the author unavailable or failing → a loud warning, never a broken build. Freshness is
//     this hook's job; correctness stays the ratchet's, and a stale-but-committed bundle still
//     fails the gate that matters.

import { spawnSync } from "node:child_process";
import { stat } from "node:fs/promises";
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

async function main() {
  const here = dirname(fileURLToPath(import.meta.url));
  const root = await findRepoRoot(here);
  if (!root) {
    log("no repo root — keeping the committed bundle.");
    return;
  }

  const author = spawnSync("uv", ["run", "python", "scripts/build_eval_bundle.py"], {
    cwd: root,
    stdio: "inherit",
  });
  if (author.error) {
    log(
      `WARNING: could not run scripts/build_eval_bundle.py (${author.error.message}) — keeping the committed bundle; the gate's ratchet still judges it.`,
    );
    return;
  }
  if (author.status !== 0) {
    log(
      `WARNING: scripts/build_eval_bundle.py exited ${author.status} — keeping the committed bundle; the gate's ratchet still judges it.`,
    );
  }
}

main().catch((err) => {
  // Never break the build over the fallback bundle.
  console.warn(`[sync-eval-bundle] skipped: ${err?.message ?? err}`);
});

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A number rendered for a reader goes through `lib/format-number` — never `toFixed`.
 *
 * `toFixed` always emits a `.`, whatever the page's language: "12.34 €" under a French
 * heading, on a cockpit read in three languages. The formatting module has existed since
 * 2026-08-15 and the sweep that was supposed to follow it never finished: on 2026-08-27 the
 * cost KPI of the Vue d'ensemble still glued `toFixed(2) + " €"` by hand. This ratchet is
 * what "finished" means — the remaining sites are FROZEN per file and may only go down.
 *
 * The frozen counts are LINES containing `toFixed(`, comments and SVG-path sites included:
 * a `toFixed` that feeds an SVG `d=` attribute or a React key is legitimate (a locale comma
 * would break the path), but distinguishing it mechanically is guesswork, so the ledger
 * freezes everything and a legitimate new site costs a deliberate +1 here — a visible act,
 * reviewed, instead of a silent regression.
 *
 * Three ways to fail, all deliberate:
 *  - a file above its frozen count → a new bare `toFixed` slipped in; route it through
 *    `lib/format-number` (or, for a genuine SVG/key site, raise the entry in this ledger
 *    in the same commit that adds it, and say why);
 *  - a file below its frozen count → debt was paid; lower the entry so it cannot silently
 *    come back;
 *  - a file not in the ledger with a count > 0 → same as above, new debt is refused.
 */
const FROZEN_TOFIXED_LINES: Record<string, number> = {
  "components/agent/agent-a-faire.tsx": 1,
  "components/agent/agent-breakdown.tsx": 1, // comment only
  "components/agent/agent-configurations.tsx": 1,
  "components/agent/agent-console.tsx": 3,
  "components/agent/agent-evaluations.tsx": 1,
  "components/agent/agent-historique.tsx": 2,
  "components/agent/prompt-tabs.tsx": 4,
  "components/agent/temporal-monitoring-breakdown.tsx": 1, // comment only
  "components/cockpit/catalog-tab-view.tsx": 2, // SVG path
  "components/cockpit/stretch-chart.tsx": 1, // SVG path
  "components/compliance/compliance-dashboard.tsx": 2,
  "components/health/health-dashboard.tsx": 1,
  "components/health/instrumentation-coverage.tsx": 1,
  "components/observability/failed-board.tsx": 1, // SVG path
  "components/observability/judge-calibration.tsx": 3, // SVG paths + a React key
  "components/observability/models-board.tsx": 3, // comment + SVG paths
  "components/observability/overview-exec.tsx": 2, // SVG path + a React key
  "components/observability/replay-panel.tsx": 14,
  "components/observability/runs-datasets.tsx": 2, // SVG paths
  "components/observability/session-theater.tsx": 1,
  "components/observability/signals-table.tsx": 1, // SVG path
  "components/observability/sparkline.tsx": 1, // SVG path
  "components/observability/workflow-runs-panel.tsx": 1,
  "components/overview/metric-sparkline.tsx": 2, // SVG points
  "components/recouvrement/recouvrement-assistant-backend.ts": 1,
  "components/reliability/reliability-dashboard.tsx": 7,
  "components/replay/replay-cassette.tsx": 4,
  "components/security/security-dashboard.tsx": 3,
  "components/sources/sources-overview.tsx": 1,
  "lib/control-registry.ts": 1, // comment only
  "lib/format-number.ts": 4, // its own docstrings, quoting the defect it replaces
};

const ROOT = join(__dirname, "..");
const SCANNED_DIRS = ["components", "app", "lib"] as const;

function* walk(dir: string): Generator<string> {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) {
      yield* walk(path);
    } else if (/\.(ts|tsx)$/.test(entry) && !/\.test\.(ts|tsx)$/.test(entry)) {
      yield path;
    }
  }
}

function countToFixedLines(path: string): number {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => line.includes("toFixed(")).length;
}

describe("bare toFixed is frozen debt (numbers read in three languages)", () => {
  const measured = new Map<string, number>();
  for (const dir of SCANNED_DIRS) {
    for (const path of walk(join(ROOT, dir))) {
      const count = countToFixedLines(path);
      if (count > 0) measured.set(relative(ROOT, path), count);
    }
  }

  it("no file exceeds its frozen count, and paid debt lowers its entry", () => {
    const regressions: string[] = [];
    const paid: string[] = [];
    for (const [file, count] of measured) {
      const frozen = FROZEN_TOFIXED_LINES[file] ?? 0;
      if (count > frozen) regressions.push(`${file}: ${count} > frozen ${frozen}`);
      else if (count < frozen) paid.push(`${file}: ${count} < frozen ${frozen} — lower the entry`);
    }
    for (const file of Object.keys(FROZEN_TOFIXED_LINES)) {
      if (!measured.has(file)) paid.push(`${file}: 0 < frozen — remove the entry`);
    }
    expect(regressions, "new bare toFixed — use lib/format-number").toEqual([]);
    expect(paid, "debt paid — tighten the ledger in the same commit").toEqual([]);
  });
});

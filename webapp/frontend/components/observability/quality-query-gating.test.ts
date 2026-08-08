import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * The two client components that fetch for the Qualité IA page, and why this ratchet reads both.
 *
 * Every gated query used to live in the dashboard, so the ratchet read one file and named it.
 * Four tabs then crossed to the evaluations view, taking six queries with them — and a
 * single-file witness would have gone green on the move by simply no longer being able to see
 * what it polices. That is the failure mode of ADR 0026 in its purest form, and it would have
 * been caused by the very change it exists to police. So the sources are a SET, each query is
 * looked up across the set, and a query found in neither is an error rather than a skip.
 */
const SOURCES = {
  dashboard: "components/observability/observability-dashboard.tsx",
  evaluations: "components/eval/eval-dashboard.tsx",
} as const;

const source = Object.fromEntries(
  Object.entries(SOURCES).map(([name, path]) => [
    name,
    readFileSync(join(process.cwd(), path), "utf8"),
  ]),
) as Record<keyof typeof SOURCES, string>;

function queryBlock(where: keyof typeof SOURCES, queryKeyPrefix: string): string {
  const text = source[where];
  const start = text.indexOf(`queryKey: ${queryKeyPrefix}`);
  if (start < 0) throw new Error(`query ${queryKeyPrefix} not found in ${SOURCES[where]}`);
  const end = text.indexOf("\n  });", start);
  if (end < 0) throw new Error(`query ${queryKeyPrefix} has no closing block in ${SOURCES[where]}`);
  return text.slice(start, end);
}

describe("quality tab query gating", () => {
  it.each([
    ["embedding skew", "evaluations", '["embedding-skew"]', 'enabled: tab === "archive"'],
    ["corpus freshness", "evaluations", '["corpus-freshness"]', 'enabled: tab === "archive"'],
    ["evaluation datasets", "evaluations", '["eval-datasets"]', 'enabled: tab === "archive"'],
    ["failed runs", "evaluations", '["failed-runs"]', 'enabled: tab === "failed"'],
    [
      "grounding drift",
      "evaluations",
      '["judge-drift", "grounding", null, period]',
      'enabled: tab === "models"',
    ],
    [
      "signal status trend",
      "dashboard",
      '["signal-status-trend", asOf, period]',
      'enabled: tab === "signals"',
    ],
    // The two the dashboard KEPT after the migration. They are read by the overview as well as
    // by the departed tabs, so they exist on both sides — and the half that stayed must be
    // gated on what still renders it, not on tab names that no longer exist here.
    ["the run archive", "dashboard", '["runs"]', 'enabled: tab === "overview"'],
    ["the model comparison", "dashboard", '["model-comparison"]', 'enabled: tab === "overview"'],
  ] as const)(
    "loads %s only in the tab that renders it",
    (_name, where, queryKeyPrefix, predicate) => {
      expect(queryBlock(where, queryKeyPrefix)).toContain(predicate);
    },
  );

  /**
   * The duplicated pair costs no extra request — but only while both sides agree on the key.
   *
   * `runs` and `model-comparison` are fetched by both components. React Query serves one cached
   * answer to both *because the key is the same string*; drift the key on one side and the page
   * silently doubles the request without any test noticing a number.
   */
  it("keeps the duplicated reads on one cache key, so the duplication stays free", () => {
    for (const key of ['queryKey: ["runs"]', 'queryKey: ["model-comparison"]']) {
      expect(source.dashboard).toContain(key);
      expect(source.evaluations).toContain(key);
    }
  });

  /** A departed tab name left behind in a gate is a query that never fires again. */
  it("leaves no gate in the dashboard naming a tab that moved out", () => {
    for (const gone of ["runs", "failed", "models", "judge"]) {
      expect(source.dashboard).not.toContain(`enabled: tab === "${gone}"`);
      expect(source.dashboard).not.toContain(`tab === "${gone}"`);
    }
  });
});

describe("quality mobile chrome", () => {
  it("keeps the tall control rail non-sticky on phones", () => {
    expect(source.dashboard).toContain("md:sticky md:-top-5 md:z-40");
    expect(source.dashboard).not.toContain('className="sticky top-0 z-30');
  });

  it("masks scrolling content up to the shell header once pinned", () => {
    expect(source.dashboard).toContain("bg-[var(--tessera-bg)]");
    expect(source.dashboard).toContain("shadow-[0_-4px_0_0_var(--tessera-bg)]");
    expect(source.dashboard).not.toContain("md:sticky md:top-0");
  });
});

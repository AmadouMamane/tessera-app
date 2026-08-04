import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const source = readFileSync(
  join(process.cwd(), "components/observability/observability-dashboard.tsx"),
  "utf8",
);

function queryBlock(queryKeyPrefix: string): string {
  const start = source.indexOf(`queryKey: ${queryKeyPrefix}`);
  if (start < 0) throw new Error(`query ${queryKeyPrefix} not found`);
  const end = source.indexOf("\n  });", start);
  if (end < 0) throw new Error(`query ${queryKeyPrefix} has no closing block`);
  return source.slice(start, end);
}

describe("quality tab query gating", () => {
  it.each([
    ["embedding skew", '["embedding-skew"]', 'enabled: tab === "runs"'],
    ["corpus freshness", '["corpus-freshness"]', 'enabled: tab === "runs"'],
    ["evaluation datasets", '["eval-datasets"]', 'enabled: tab === "runs"'],
    ["failed runs", '["failed-runs"]', 'enabled: tab === "failed"'],
    ["signal status trend", '["signal-status-trend", asOf, period]', 'enabled: tab === "signals"'],
    ["grounding drift", '["judge-drift", "grounding", asOf, period]', 'enabled: tab === "models"'],
  ])("loads %s only in the tab that renders it", (_name, queryKeyPrefix, predicate) => {
    expect(queryBlock(queryKeyPrefix)).toContain(predicate);
  });
});

describe("quality mobile chrome", () => {
  it("keeps the tall control rail non-sticky on phones", () => {
    expect(source).toContain("md:sticky md:-top-5 md:z-40");
    expect(source).not.toContain('className="sticky top-0 z-30');
  });

  it("masks scrolling content up to the shell header once pinned", () => {
    expect(source).toContain("bg-[var(--tessera-bg)]");
    expect(source).toContain("shadow-[0_-4px_0_0_var(--tessera-bg)]");
    expect(source).not.toContain("md:sticky md:top-0");
  });
});

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("donut totals", () => {
  it.each([
    "components/reliability/reliability-dashboard.tsx",
    "components/security/security-dashboard.tsx",
  ])("keeps an empty measured total distinct from its safe denominator in %s", (file) => {
    const source = readFileSync(join(root, file), "utf8");
    expect(source).toContain("const measuredTotal = slices.reduce(");
    expect(source).toContain("const denominator = measuredTotal || 1;");
    expect(source).toContain("{measuredTotal}");
    expect(source).not.toContain("const total = slices.reduce((s, x) => s + x.count, 0) || 1;");
  });
});

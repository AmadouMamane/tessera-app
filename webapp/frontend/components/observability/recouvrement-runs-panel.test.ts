import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("Recouvrement Cockpit run panel", () => {
  it("is wired into the quality dashboard without replacing existing tabs", () => {
    const dashboard = readFileSync(
      join(process.cwd(), "components/observability/observability-dashboard.tsx"),
      "utf8",
    );
    const panel = readFileSync(
      join(process.cwd(), "components/observability/recouvrement-runs-panel.tsx"),
      "utf8",
    );

    expect(dashboard).toContain('"recouvrement"');
    expect(dashboard).toContain("fetchRecouvrementRuns");
    expect(dashboard).toContain("RecouvrementRunsPanel");
    expect(panel).toContain("Timeline métier");
    expect(panel).toContain("Actions sensibles");
    expect(panel).toContain("no_external_effect");
    expect(panel).toContain("no_uncontrolled_external_effect");
  });
});

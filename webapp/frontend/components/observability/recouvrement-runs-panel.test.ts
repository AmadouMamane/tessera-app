import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("Workflow runs panel (ADR 0017 Phase A)", () => {
  it("is generic, wired through the dimension-filtered business-runs read", () => {
    const dashboard = readFileSync(
      join(process.cwd(), "components/observability/observability-dashboard.tsx"),
      "utf8",
    );
    const panel = readFileSync(
      join(process.cwd(), "components/observability/workflow-runs-panel.tsx"),
      "utf8",
    );

    // The tab survives Phase A (dissolved in Phase C); its data path is generic.
    expect(dashboard).toContain('"recouvrement"');
    expect(dashboard).toContain("fetchBusinessRuns");
    expect(dashboard).toContain("WorkflowRunsPanel");
    // Agent-specific copy enters through props, not the component.
    expect(dashboard).toContain('title="Runs Recouvrement"');
    expect(panel).not.toContain('"Runs Recouvrement"');
    expect(panel).toContain("Timeline métier");
    expect(panel).toContain("Actions sensibles");
    expect(panel).toContain("no_external_effect");
    expect(panel).toContain("no_uncontrolled_external_effect");
  });

  it("keeps the deprecated shim until the tab dissolves (Phase C)", () => {
    const shim = readFileSync(
      join(process.cwd(), "components/observability/recouvrement-runs-panel.tsx"),
      "utf8",
    );
    expect(shim).toContain("@deprecated");
    expect(shim).toContain("WorkflowRunsPanel as RecouvrementRunsPanel");
  });
});

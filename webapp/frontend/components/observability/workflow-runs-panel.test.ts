import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * WorkflowRunsPanel — the generic business-runs panel (ADR 0017). The hardcoded "recouvrement"
 * quality-dashboard tab, its `recouvrement-runs-panel` shim, the `fetchRecouvrementRuns` alias
 * and the `/observability/recouvrement-runs` route dissolved in Phase C (step 4). This panel is
 * the surviving read model; these source-level assertions pin its generic contract.
 */
const panel = readFileSync(
  join(process.cwd(), "components/observability/workflow-runs-panel.tsx"),
  "utf8",
);

describe("WorkflowRunsPanel (generic business-runs panel)", () => {
  it("is agent-agnostic: agent copy enters through props, business grammar rendered generically", () => {
    // Agent-specific copy is a prop, never baked into the component.
    expect(panel).not.toContain('"Runs Recouvrement"');
    expect(panel).toContain("Chronologie métier");
    expect(panel).toContain("Actions sensibles");
    expect(panel).toContain("no_external_effect");
    expect(panel).toContain("no_uncontrolled_external_effect");
  });

  it("supports caller-controlled (URL-derived) run selection", () => {
    expect(panel).toContain("selectedTurnId");
    expect(panel).toContain("onSelectTurn");
  });
});

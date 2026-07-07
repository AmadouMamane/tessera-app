import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * BR-01 §5 wiring guard for the AGENT / Métier surface (registre des rails v1.3).
 *
 * These are source-level assertions (same style as the sibling panel tests): they pin the
 * §5 contract — capability + run selection derive from the URL (deep-link, never local
 * state), the global as-of is propagated to the business reads, and the active temporal mode
 * is displayed (Live by default) — so a refactor cannot silently drop the compliance wiring.
 */
const metier = readFileSync(join(process.cwd(), "components/agent/agent-metier.tsx"), "utf8");
const panel = readFileSync(
  join(process.cwd(), "components/observability/workflow-runs-panel.tsx"),
  "utf8",
);

describe("agent-metier BR-01 §5 compliance wiring", () => {
  it("derives capability + run selection from the URL (deep-link), not local state", () => {
    expect(metier).toContain('searchParams.get("capability_id")');
    expect(metier).toContain('searchParams.get("turn_id")');
    expect(metier).toContain("router.replace");
    expect(metier).toContain("updateParams({ capability_id");
    expect(metier).toContain("updateParams({ turn_id");
    // The capability selection is no longer a private component state.
    expect(metier).not.toContain("setSelectedCapabilityId");
  });

  it("propagates the global as-of to both business reads and freezes polling", () => {
    expect(metier).toContain("resolveMetierAsOf");
    expect(metier).toContain("at: asOf ?? undefined");
    expect(metier).toContain("refetchInterval: asOf ? false : 5_000");
  });

  it("shows the active temporal mode (Live by default)", () => {
    expect(metier).toContain("TemporalModeBadge");
    expect(metier).toContain('t("temporal.live")');
  });

  it("lets the drilled-down run be controlled (URL-derived) by the caller", () => {
    expect(panel).toContain("selectedTurnId");
    expect(panel).toContain("onSelectTurn");
  });
});

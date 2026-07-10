import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { plottablePoints } from "./sparkline";

const source = readFileSync(join(__dirname, "sparkline.tsx"), "utf-8");

describe("plottablePoints", () => {
  it("keeps only real values and remembers where they sat", () => {
    const points = [
      { bucket: "2026-07-07", value_pct: 100, status: "scored" },
      { bucket: "2026-07-08", value_pct: null, status: "not_applicable" },
      { bucket: "2026-07-09", value_pct: 80, status: "scored" },
    ];
    expect(plottablePoints(points)).toEqual([
      { x: 0, y: 100 },
      { x: 2, y: 80 },
    ]);
  });

  it("treats a null day as an absence, never as a zero", () => {
    const points = [
      { bucket: "2026-07-07", value_pct: null, status: "not_applicable" },
      { bucket: "2026-07-08", value_pct: null, status: "unknown" },
    ];
    expect(plottablePoints(points)).toEqual([]);
  });
});

describe("the sparkline is delivered ready but unwired (P3 item 19)", () => {
  it("renders nothing below two real points — one dot is not a trend", () => {
    // Guarded in the component; asserted here so a future edit cannot quietly drop it.
    expect(source).toContain("if (plotted.length < 2 || points.length < 2) return null;");
  });

  it("breaks the line across a gap instead of bridging it", () => {
    expect(source).toContain("a gap (null day) breaks the polyline instead of bridging it");
    expect(source).toContain("if (run.length > 1) segments.push");
  });

  it("carries an accessible name", () => {
    expect(source).toContain('role="img"');
    expect(source).toContain("aria-label={label}");
  });

  it("is mounted by nobody — on purpose", () => {
    // If this ever fails, the wiring decision was taken: update the component's header and
    // this test together, so "ready but unwired" never silently becomes "quietly wired".
    const mounted = ["agent-metier.tsx", "workflow-runs-panel.tsx"].some((file) =>
      readFileSync(
        join(__dirname, "..", file.startsWith("agent") ? "agent" : "observability", file),
        "utf-8",
      ).includes("<Sparkline"),
    );
    expect(mounted).toBe(false);
  });
});

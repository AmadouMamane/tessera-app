import { describe, expect, it } from "vitest";

import type { ReplayBundle } from "@/lib/api/schemas";
import { buildCassetteTrace } from "@/lib/replay-cassette";

// XT-01 — the cassette trace is a pure projection of the persisted S2 record:
// real spans, real offsets when captured, real tool children, and an honest
// unpositioned/empty rendering for bundles that predate the capture.

function bundle(overrides: Partial<ReplayBundle>): ReplayBundle {
  return {
    bundle_id: "b1",
    captured_at: "2026-07-22T10:00:00+00:00",
    language: "fr",
    question: "q",
    context: "c",
    original_answer: "a",
    original_model: "m",
    original_score: 0.8,
    ...overrides,
  };
}

describe("buildCassetteTrace", () => {
  it("positions spans by their real offsets, nests tools under their node, appends the reporter", () => {
    const trace = buildCassetteTrace(
      bundle({
        latency_ms: { router: 5, dispatch: 120, simulator: 80 },
        node_starts: { router: 0, dispatch: 10, simulator: 30 },
        reporter_ms: 400,
        tool_calls: [
          { name: "loan_simulate", node: "simulator", succeeded: true, duration_ms: 12.5 },
        ],
      }),
    );
    expect(trace).not.toBeNull();
    expect(trace?.positioned).toBe(true);
    expect(trace?.spans.map((s) => s.key)).toEqual(["router", "dispatch", "simulator", "reporter"]);
    const simulator = trace?.spans.find((s) => s.key === "simulator");
    expect(simulator?.tools).toEqual([
      { name: "loan_simulate", succeeded: true, duration_ms: 12.5 },
    ]);
    // Timed phase ends at max(start+duration)=130; the reporter streams after it.
    const reporter = trace?.spans.at(-1);
    expect(reporter?.start_ms).toBe(130);
    expect(trace?.total_ms).toBe(530);
    expect(trace?.orphan_tools).toEqual([]);
  });

  it("renders a pre-offset capture unpositioned, with no fabricated total", () => {
    const trace = buildCassetteTrace(bundle({ latency_ms: { router: 5, dispatch: 120 } }));
    expect(trace?.positioned).toBe(false);
    expect(trace?.spans.every((s) => s.start_ms === null)).toBe(true);
    expect(trace?.total_ms).toBeNull();
  });

  it("keeps tool calls whose node was not timed as explicit orphans", () => {
    const trace = buildCassetteTrace(
      bundle({
        latency_ms: { router: 5 },
        tool_calls: [{ name: "card_block", node: "", succeeded: false, duration_ms: 3 }],
      }),
    );
    expect(trace?.orphan_tools).toEqual([{ name: "card_block", succeeded: false, duration_ms: 3 }]);
  });

  it("says null for a bundle that recorded no execution shape at all", () => {
    expect(buildCassetteTrace(bundle({}))).toBeNull();
  });
});

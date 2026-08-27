import { describe, expect, it } from "vitest";

import { rateMarginPts } from "./rate-confidence";

describe("rateMarginPts — a rate carries its power", () => {
  it("matches the known Wilson 95% interval at p=0.5, n=100 (≈ ±9.6 pts)", () => {
    const m = rateMarginPts(50, 100);
    expect(m).not.toBeNull();
    expect(m as number).toBeGreaterThan(9);
    expect(m as number).toBeLessThan(10.5);
  });

  it("shrinks as the sample grows", () => {
    const small = rateMarginPts(50, 100) as number;
    const large = rateMarginPts(500, 1000) as number;
    expect(large).toBeLessThan(small);
  });

  it("never claims exactness at the edges (p=0 and p=1 still carry a margin)", () => {
    // The naive ±z·√(p(1−p)/n) collapses to 0 here — maximal confidence from minimal
    // knowledge. Wilson does not, which is why it was chosen.
    expect(rateMarginPts(0, 100) as number).toBeGreaterThan(1);
    expect(rateMarginPts(100, 100) as number).toBeGreaterThan(1);
  });

  it("returns null — not 0 — when no margin can be computed", () => {
    expect(rateMarginPts(0, 0)).toBeNull();
    expect(rateMarginPts(5, 4)).toBeNull();
    expect(rateMarginPts(-1, 10)).toBeNull();
    expect(rateMarginPts(Number.NaN, 10)).toBeNull();
  });

  it("stays within [0, 100] points", () => {
    for (const [good, n] of [
      [1, 2],
      [3, 5],
      [49, 67],
      [353, 415],
    ] as const) {
      const m = rateMarginPts(good, n) as number;
      expect(m).toBeGreaterThan(0);
      expect(m).toBeLessThanOrEqual(100);
    }
  });
});

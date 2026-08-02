/**
 * A curve is the row's own number, once per bucket — and an empty bucket is a HOLE.
 *
 * Two failures are being held off here, and both look like working charts.
 *
 * The first is a second derivation. Before 2026-08-01 exactly one control had a curve, and it
 * had one because `overview-dashboard.tsx` named it by id and mapped `trend.buckets`. Giving
 * the other eight a curve the same way — each with its own little "compute a trend" — is how a
 * falling line ends up above a rising number with both defensible in isolation. `readControlSeries`
 * therefore calls `readControl`, the same function that produced the value, and plots the ratio
 * that function reports.
 *
 * The second is zero-filling. A bucket with no traffic and a bucket that measured zero draw as
 * the same low point; on a leak rate they mean "a quiet week" and "a clean week". They must not
 * be the same pixel.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  type ControlSeriesBucket,
  bucketWidthHours,
  hasDrawableCurve,
  readControl,
  readControlSeries,
} from "./control-registry";

/** A bucket whose PII source saw `turns` turns, `leaks` of which leaked. */
const piiBucket = (index: number, turns: number, leaks: number): ControlSeriesBucket => ({
  index,
  since: `2026-07-2${index}T00:00:00Z`,
  until: `2026-07-2${index + 1}T00:00:00Z`,
  payload: {
    pii: {
      n_turns: turns,
      n_with_leak: leaks,
      leak_rate: turns === 0 ? 0 : leaks / turns,
      total_leaked: leaks,
      examples: [],
    },
  },
});

describe("a curve plots the number the row displays", () => {
  it("reads each bucket through the SAME function that produced the value", () => {
    const buckets = [piiBucket(0, 100, 2), piiBucket(1, 100, 5)];
    const curve = readControlSeries(buckets, "pii");
    // Not "some plausible series" — exactly what `readControl` reports for each bucket.
    expect(curve).toEqual(buckets.map((b) => readControl("pii", b.payload)?.ratio));
    expect(curve).toEqual([0.02, 0.05]);
  });

  it("keeps the ratio and the rendered value in step", () => {
    const reading = readControl("pii", piiBucket(0, 100, 2).payload);
    expect(reading?.value).toBe("2.00%");
    expect(reading?.ratio).toBe(0.02);
  });

  it("plots the unrounded ratio, so a curve is not flattened by display precision", () => {
    // Faithfulness renders whole percents. Two buckets 0.4 points apart show the SAME text
    // and are genuinely different measurements — a curve drawn from the rendered string
    // would flatten them, which is why `ratio` exists next to `value`.
    const slo = (n_good: number): ControlSeriesBucket => ({
      index: 0,
      since: "s",
      until: "u",
      payload: {
        slo: {
          metric: "rag.faithfulness.mean",
          threshold: 0.7,
          target: 0.95,
          n: 1000,
          n_good,
          n_bad: 1000 - n_good,
          good_rate: n_good / 1000,
          error_budget: 0.05,
          budget_consumed: 0,
          budget_remaining: 1,
          burn_rate: 0,
          burn_rate_fast: 0,
          breaching: false,
        },
      },
    });
    const [a, b] = [slo(902), slo(898)];
    expect(readControl("faithfulness", a.payload)?.value).toBe(
      readControl("faithfulness", b.payload)?.value,
    );
    expect(readControlSeries([a, b], "faithfulness")).toEqual([0.902, 0.898]);
  });
});

describe("an empty bucket is a hole, never a zero", () => {
  it("returns null for a bucket whose window held no traffic", () => {
    // The middle bucket saw NOTHING. A leak rate of 0 there would be the most reassuring
    // number this control can show, produced by a week nobody observed.
    const curve = readControlSeries(
      [piiBucket(0, 100, 3), piiBucket(1, 0, 0), piiBucket(2, 100, 1)],
      "pii",
    );
    expect(curve).toEqual([0.03, null, 0.01]);
    expect(curve[1]).not.toBe(0);
  });

  it("returns null for a bucket whose source is missing entirely", () => {
    const curve = readControlSeries(
      [piiBucket(0, 50, 1), { index: 1, since: "s", until: "u", payload: {} }],
      "pii",
    );
    expect(curve).toEqual([0.02, null]);
  });

  it("distinguishes a measured zero from an unmeasured one", () => {
    // A hundred turns and no leaks IS a measurement, and it must survive as 0 rather than
    // being folded into the same null as "nothing happened".
    expect(readControlSeries([piiBucket(0, 100, 0)], "pii")).toEqual([0]);
    expect(readControlSeries([piiBucket(0, 0, 0)], "pii")).toEqual([null]);
  });
});

describe("one point is not a trend", () => {
  it("refuses to call a single measured bucket a curve", () => {
    expect(hasDrawableCurve([null, 0.4, null])).toBe(false);
    expect(hasDrawableCurve([])).toBe(false);
    expect(hasDrawableCurve([null, null])).toBe(false);
  });

  it("draws once two measured buckets exist, even with a hole between them", () => {
    expect(hasDrawableCurve([0.4, null, 0.6])).toBe(true);
  });
});

describe("how wide a slice is, read off the report and not guessed", () => {
  const report = (since: string, until: string, n_buckets: number) => ({ since, until, n_buckets });

  it("divides the report's own bounds by its own count", () => {
    // 7 days over 14 buckets — the cockpit's default window, after the backend stopped cutting
    // every window into a flat eight.
    expect(bucketWidthHours(report("2026-07-26T10:00:00Z", "2026-08-02T10:00:00Z", 14))).toBe(12);
    expect(bucketWidthHours(report("2026-08-01T10:00:00Z", "2026-08-02T10:00:00Z", 12))).toBe(2);
    expect(bucketWidthHours(report("2026-07-03T10:00:00Z", "2026-08-02T10:00:00Z", 30))).toBe(24);
  });

  it("says nothing rather than something wrong when there is no window", () => {
    // The count is the BACKEND's choice (`buckets_for_window`). A front that recomputed it
    // from the period key would print a confident wrong width the day that choice changes —
    // which is precisely the day this function starts mattering.
    expect(bucketWidthHours(undefined)).toBeNull();
    expect(bucketWidthHours(report("2026-08-02T10:00:00Z", "2026-08-02T10:00:00Z", 8))).toBeNull();
    expect(
      bucketWidthHours(report(null as unknown as string, "2026-08-02T10:00:00Z", 8)),
    ).toBeNull();
    expect(bucketWidthHours(report("2026-07-26T10:00:00Z", "2026-08-02T10:00:00Z", 0))).toBeNull();
  });
});

describe("the resolution is decided once, by the window", () => {
  it("is not pinned at either call site", () => {
    // Vue d'ensemble and Qualité IA draw the SAME control's curve. A `buckets:` passed by one
    // of them is not a local preference — it is that control having two shapes depending on
    // which page you opened, which is the divergence class the registry exists to end.
    for (const file of [
      "components/overview/overview-dashboard.tsx",
      "components/observability/observability-dashboard.tsx",
    ]) {
      const source = readFileSync(join(process.cwd(), file), "utf8");
      const call = /fetchControlSeries\(([\s\S]{0,220}?)\)\s*,?\s*$/m.exec(source)?.[1] ?? "";
      expect(source, file).toContain("fetchControlSeries");
      expect(call, file).not.toContain("buckets");
    }
  });
});

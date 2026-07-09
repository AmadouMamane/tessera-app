import { describe, expect, it } from "vitest";
import { z } from "zod";

import { SNAPSHOT_SIGNALS, selectSignal } from "@/lib/overview-snapshot";

const SloSchema = z.object({ good_rate: z.number(), breaching: z.boolean() });

const snapshot = {
  scope: { agent: "all" },
  signals: {
    slo: { data: { good_rate: 0.97, breaching: false }, report: { honoured: ["agent"] } },
    // The backend could not compute this one: honest-absent, not a fabricated zero.
    cost: { report: { unavailable: true } },
    trend: { data: null, report: {} },
  },
  meta: { upstream_reads: 3 },
};

describe("selectSignal", () => {
  it("returns the slice, validated by the card's own schema", () => {
    expect(selectSignal(snapshot, "slo", SloSchema)).toEqual({ good_rate: 0.97, breaching: false });
  });

  it("a signal the backend could not compute stays undefined — never {} and never 0", () => {
    const cost = selectSignal(snapshot, "cost", z.object({ total_eur: z.number() }));
    expect(cost).toBeUndefined();
  });

  it("an explicit null payload is absent, not a zero", () => {
    expect(
      selectSignal(snapshot, "trend", z.object({ points: z.array(z.number()) })),
    ).toBeUndefined();
  });

  it("a signal missing from the snapshot entirely is undefined", () => {
    expect(selectSignal(snapshot, "anomalies", z.object({ n: z.number() }))).toBeUndefined();
  });

  it("no snapshot at all (still loading) is undefined, not an error", () => {
    expect(selectSignal(undefined, "slo", SloSchema)).toBeUndefined();
  });

  it("a payload that drifted from the card's contract degrades to honest-empty", () => {
    // If the snapshot ever stopped matching its route, the card must show its empty state
    // rather than render a half-parsed object. The backend parity test is the real guard;
    // this is the client refusing to guess.
    const drifted = { signals: { slo: { data: { good_rate: "not a number" } } } };
    expect(selectSignal(drifted, "slo", SloSchema)).toBeUndefined();
  });

  it("pins the signal set the backend actually ships", () => {
    // Mirrors `snapshot_signal_ids()`. If the backend adds one, this list must learn about it
    // deliberately — a card selecting an id the snapshot never carries would silently read empty.
    expect([...SNAPSHOT_SIGNALS]).toEqual([
      "scores",
      "slo",
      "trend",
      "funnel",
      "gating",
      "toxicity",
      "pii_leak",
      "cost",
      "anomalies",
      "what_changed",
    ]);
  });
});

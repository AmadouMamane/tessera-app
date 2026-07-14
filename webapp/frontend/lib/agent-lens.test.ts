// The RATCHET for the breakdown lens: the backend's honesty contract, enforced in the front.
//
// The spine already refuses to lie about a slice — each signal returns a `report` naming the
// scope dimensions it HONOURED and those it IGNORED, so "the filter is shown but silently
// ignored" is unrepresentable server-side. Nothing carried that guarantee across the wire: the
// report reached the client (it survives zod) and no component had ever read it.
//
// These tests are the client's half of the contract, and they are written to go RED under their
// own mutation:
//
//   · swap `selectHonouredSignal` for `selectSignal` in `agent-lens.ts` → the not-honoured and
//     org-wide cases start yielding numbers → red.
//   · delete the `isOrgWide` guard in `buildAlarmLens` → an org-wide signal gets a per-agent
//     table built from a neighbouring signal's rows → red.
//   · make an unreadable report fall through to the data → the no-report case yields a value → red.
//
// A number nobody can prove is a number nobody should read.
import { describe, expect, it } from "vitest";

import { buildAlarmLens, buildQualityLens, planLens } from "@/lib/agent-lens";
import type { OverviewSnapshot } from "@/lib/overview-snapshot";

const SLO_DATA = {
  metric: "faithfulness",
  threshold: 0.95,
  target: 0.95,
  n: 20,
  n_good: 6,
  n_bad: 14,
  good_rate: 0.3,
  error_budget: 0.05,
  budget_consumed: 1,
  budget_remaining: 0,
  burn_rate: 14,
  burn_rate_fast: 14,
  breaching: true,
};

/** A report the spine would emit for a per-agent read that HONOURED the agent dimension. */
const HONOURED = {
  honoured: ["agent", "time"],
  ignored: [],
  org_wide: false,
  synthetic: false,
  source: "spine",
  unavailable: false,
};

function snapshot(
  report: Record<string, unknown>,
  data: Record<string, unknown> = SLO_DATA,
): OverviewSnapshot {
  return { signals: { slo: { data, report } } };
}

/** Row `i`, or a loud failure. An absent row is a broken test, never a silently skipped one. */
function row<T>(rows: readonly T[], i: number): T {
  const value = rows[i];
  if (value === undefined) throw new Error(`no row at index ${i} (got ${rows.length})`);
  return value;
}

describe("planLens — the page's question decides the columns", () => {
  it("a breaching SLO puts the table in the alarm lens", () => {
    expect(planLens(snapshot(HONOURED))).toEqual({ kind: "alarm", signalId: "slo" });
  });

  it("no breach ⇒ the quality lens", () => {
    const quiet = snapshot(HONOURED, { ...SLO_DATA, breaching: false, good_rate: 0.99 });
    expect(planLens(quiet)).toEqual({ kind: "quality" });
  });

  it("a breaching ORG-WIDE signal masks the table — it has no per-agent substrate", () => {
    // `firewall` omits AGENT in capabilities.py; the registry mirrors it. The table is not
    // "empty" for such a signal, it is INAPPLICABLE — and the Fiche signal says why.
    expect(planLens(snapshot(HONOURED), "firewall")).toEqual({
      kind: "masked",
      signalId: "firewall",
    });
    expect(planLens(snapshot(HONOURED), "refusal")).toEqual({
      kind: "masked",
      signalId: "refusal",
    });
    expect(planLens(snapshot(HONOURED), "audit_integrity")).toEqual({
      kind: "masked",
      signalId: "audit_integrity",
    });
  });

  it("no snapshot at all is not an alarm — a witness that cannot see may not cry breach", () => {
    expect(planLens(undefined)).toEqual({ kind: "quality" });
  });
});

describe("the ratchet: no lens may display a number the report declares NOT HONOURED", () => {
  it("agent IGNORED ⇒ the cell is refused, and says so", () => {
    const ignored = snapshot({ ...HONOURED, honoured: ["time"], ignored: ["agent"] });
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "a1", snapshot: ignored }]);
    expect(lens.kind).toBe("alarm");
    if (lens.kind !== "alarm") return;
    expect(row(lens.rows, 0)).toMatchObject({
      agentId: "a1",
      value: null,
      gapPp: null,
      nBad: null,
      refusal: "not-honoured",
    });
  });

  it("a report saying ORG-WIDE ⇒ refused, even though the data is right there", () => {
    const orgWide = snapshot({ ...HONOURED, org_wide: true });
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "a1", snapshot: orgWide }]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(row(lens.rows, 0).value).toBeNull();
    expect(row(lens.rows, 0).refusal).toBe("org-wide");
  });

  it("a report saying UNAVAILABLE ⇒ refused", () => {
    const dead = snapshot({ ...HONOURED, unavailable: true });
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "a1", snapshot: dead }]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(row(lens.rows, 0).refusal).toBe("unavailable");
  });

  it("NO readable report ⇒ refused — the slice cannot be proven, so it is not shown", () => {
    // ADR 0026: a witness that cannot see reports a blind spot; it may never report "ok".
    const noReport: OverviewSnapshot = { signals: { slo: { data: SLO_DATA } } };
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "a1", snapshot: noReport }]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(row(lens.rows, 0).value).toBeNull();
    expect(row(lens.rows, 0).refusal).toBe("no-report");
  });

  it("an ORG-WIDE signal never gets a per-agent table, whatever the rows would say", () => {
    const lens = buildAlarmLens("firewall", snapshot(HONOURED), [
      { agentId: "a1", snapshot: snapshot(HONOURED) },
    ]);
    expect(lens).toEqual({ kind: "masked", signalId: "firewall" });
  });

  it("the quality lens is gated the same way — it is not a back door", () => {
    const ignored = snapshot({ ...HONOURED, honoured: ["time"], ignored: ["agent"] });
    const lens = buildQualityLens([{ agentId: "a1", snapshot: ignored }]);
    expect(row(lens.rows, 0)).toMatchObject({
      faithfulness: null,
      faithfulnessRefusal: "not-honoured",
      hallucination: null,
    });
  });
});

describe("the alarm lens names the culprit", () => {
  const heavy = snapshot(HONOURED, { ...SLO_DATA, n: 40, n_bad: 14, good_rate: 0.65 });
  const light = snapshot(HONOURED, { ...SLO_DATA, n: 20, n_bad: 4, good_rate: 0.8 });
  const one = snapshot(HONOURED, { ...SLO_DATA, n: 7, n_bad: 1, good_rate: 0.857 });

  it("sorts by contribution, descending", () => {
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [
      { agentId: "light", snapshot: light },
      { agentId: "one", snapshot: one },
      { agentId: "heavy", snapshot: heavy },
    ]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(lens.rows.map((r) => r.agentId)).toEqual(["heavy", "light", "one"]);
    expect(lens.rows.map((r) => r.nBad)).toEqual([14, 4, 1]);
  });

  it("a refused agent sinks below every agent that has a number", () => {
    const blind = snapshot({ ...HONOURED, honoured: ["time"], ignored: ["agent"] });
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [
      { agentId: "blind", snapshot: blind },
      { agentId: "one", snapshot: one },
    ]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(lens.rows.map((r) => r.agentId)).toEqual(["one", "blind"]);
  });

  it("states the gap to the SLO target in percentage points", () => {
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "heavy", snapshot: heavy }]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    // 0.65 observed vs 0.95 target ⇒ −30 pp.
    expect(row(lens.rows, 0).gapPp).toBeCloseTo(-30, 6);
  });

  it("carries the org total beside the sum of the slices — it does NOT smooth them", () => {
    // The org's own SLO read says 19 bad; the slices sum to 19 here, but the lens reports BOTH
    // numbers and lets the footer state the relation. Equality is a coincidence to be checked,
    // never an invariant to be assumed: a handed-off journey touches two agents and counts once.
    const org = snapshot(HONOURED, { ...SLO_DATA, n: 67, n_bad: 19 });
    const lens = buildAlarmLens("slo", org, [
      { agentId: "heavy", snapshot: heavy },
      { agentId: "light", snapshot: light },
      { agentId: "one", snapshot: one },
    ]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(lens.sumNBad).toBe(19);
    expect(lens.orgNBad).toBe(19);
    expect(lens.orgN).toBe(67);
  });

  it("n = 0 is 'no sample', never a fabricated 0 % — the cell stays empty", () => {
    const empty = snapshot(HONOURED, { ...SLO_DATA, n: 0, n_bad: 0, good_rate: 0 });
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "quiet", snapshot: empty }]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(row(lens.rows, 0)).toMatchObject({ value: null, gapPp: null, nBad: null, n: 0 });
  });
});

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

import {
  buildAlarmLens,
  buildComplianceLens,
  buildObservabilityLens,
  buildProofLens,
  buildQualityLens,
  buildReliabilityLens,
  buildSecurityLens,
  planLens,
} from "@/lib/agent-lens";
import type { OverviewSnapshot } from "@/lib/overview-snapshot";
import { readSignalFocus, registryIdFor } from "@/lib/signal-focus";
import { isOrgWide } from "@/lib/signal-registry";

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

// ── The domain lenses (Sécurité / Conformité / Fiabilité) ride the SAME gate ────────────────
//
// The wire shapes below are the LIVE measured payloads (2026-07-15, `?agent=<id>&signals=…`):
// support-client answered pii_leak {n_turns:7, n_with_leak:0}, tool_validity {total:9521,
// denied:133, errored:0}, governance {total:1}, audit_count {entry_count:36193}, cost
// {n_turns:7, total_tokens:11124} — and hello/turn/duplex answered the same shapes at zero.

const DOMAIN_DATA: Record<string, Record<string, unknown>> = {
  pii_leak: { n_turns: 7, n_with_leak: 0, leak_rate: 0.0, total_leaked: 0 },
  toxicity: { n_turns: 7, n_toxic: 0, toxicity_rate: 0.0 },
  tool_validity: { total: 9521, allowed: 9388, denied: 133, errored: 0 },
  governance: { available: true, total: 1, by_kind: { routing: 1 } },
  audit_count: { entry_count: 36193, agent: "support-client" },
  cost: { n_turns: 7, total_tokens: 11124, mean_tokens: 1589.14 },
  anomalies: { n_anomalous: 0, n_sessions: 7, sessions: [] },
  conformance: { conformance_rate: 1.0, n_calls: 9521, n_violations: 0, violations: [] },
};

function domainSnapshot(
  report: Record<string, unknown>,
  data: Record<string, Record<string, unknown>> = DOMAIN_DATA,
): OverviewSnapshot {
  return {
    signals: Object.fromEntries(Object.entries(data).map(([id, d]) => [id, { data: d, report }])),
  };
}

describe("the domain lenses are gated the same way — none of them is a back door", () => {
  it("security: agent IGNORED ⇒ every cell refused, and says so", () => {
    const ignored = domainSnapshot({ ...HONOURED, honoured: ["time"], ignored: ["agent"] });
    const lens = buildSecurityLens([{ agentId: "a1", snapshot: ignored }]);
    expect(row(lens.rows, 0)).toMatchObject({
      piiLeaks: null,
      piiRefusal: "not-honoured",
      toxCount: null,
      toxRefusal: "not-honoured",
      guardDenied: null,
      guardRefusal: "not-honoured",
    });
  });

  it("security: a report saying ORG-WIDE ⇒ refused, even though the data is right there", () => {
    // THE ratchet the mutation test targets: force a security column onto an org-wide
    // signal and this goes red — the data is present, the report refuses the slice.
    const orgWide = domainSnapshot({ ...HONOURED, org_wide: true });
    const lens = buildSecurityLens([{ agentId: "a1", snapshot: orgWide }]);
    expect(row(lens.rows, 0).piiLeaks).toBeNull();
    expect(row(lens.rows, 0).piiRefusal).toBe("org-wide");
    expect(row(lens.rows, 0).guardDenied).toBeNull();
    expect(row(lens.rows, 0).guardRefusal).toBe("org-wide");
  });

  it("security: UNAVAILABLE ⇒ refused; NO readable report ⇒ refused", () => {
    const dead = domainSnapshot({ ...HONOURED, unavailable: true });
    expect(row(buildSecurityLens([{ agentId: "a1", snapshot: dead }]).rows, 0).piiRefusal).toBe(
      "unavailable",
    );
    const noReport: OverviewSnapshot = {
      signals: Object.fromEntries(Object.entries(DOMAIN_DATA).map(([id, d]) => [id, { data: d }])),
    };
    expect(row(buildSecurityLens([{ agentId: "a1", snapshot: noReport }]).rows, 0).piiRefusal).toBe(
      "no-report",
    );
  });

  it("security: one signal's refusal empties ITS cells only — never its neighbours'", () => {
    const mixed: OverviewSnapshot = {
      signals: {
        pii_leak: {
          data: DOMAIN_DATA.pii_leak,
          report: { ...HONOURED, honoured: ["time"], ignored: ["agent"] },
        },
        toxicity: { data: DOMAIN_DATA.toxicity, report: HONOURED },
        tool_validity: { data: DOMAIN_DATA.tool_validity, report: HONOURED },
      },
    };
    const r = row(buildSecurityLens([{ agentId: "a1", snapshot: mixed }]).rows, 0);
    expect(r.piiRefusal).toBe("not-honoured");
    expect(r.toxCount).toBe(0);
    expect(r.toxN).toBe(7);
    expect(r.guardDenied).toBe(133);
    expect(r.guardTotal).toBe(9521);
  });

  it("security: n = 0 is 'no sample', never a fabricated 0-of-0 — and it is NOT a refusal", () => {
    const empty = domainSnapshot(HONOURED, {
      pii_leak: { n_turns: 0, n_with_leak: 0 },
      toxicity: { n_turns: 0, n_toxic: 0 },
      tool_validity: { total: 0, allowed: 0, denied: 0, errored: 0 },
    });
    const r = row(buildSecurityLens([{ agentId: "quiet", snapshot: empty }]).rows, 0);
    expect(r).toMatchObject({
      piiLeaks: null,
      piiN: 0,
      piiRefusal: "no-sample",
      toxRefusal: "no-sample",
      guardRefusal: "no-sample",
    });
  });

  it("compliance: counts are honest at ZERO — a proven read that found nothing is a 0, not a dash", () => {
    const zeroed = domainSnapshot(HONOURED, {
      governance: { available: true, total: 0 },
      audit_count: { entry_count: 0 },
    });
    const r = row(buildComplianceLens([{ agentId: "hello-agent", snapshot: zeroed }]).rows, 0);
    expect(r).toMatchObject({
      governedActs: 0,
      governedRefusal: null,
      ledgerEntries: 0,
      ledgerRefusal: null,
    });
  });

  it("compliance: agent IGNORED ⇒ refused — 36 193 ledger entries do not excuse an unproven slice", () => {
    const ignored = domainSnapshot({ ...HONOURED, honoured: ["time"], ignored: ["agent"] });
    const r = row(buildComplianceLens([{ agentId: "a1", snapshot: ignored }]).rows, 0);
    expect(r).toMatchObject({
      governedActs: null,
      governedRefusal: "not-honoured",
      ledgerEntries: null,
      ledgerRefusal: "not-honoured",
    });
  });

  it("reliability: honoured values come through; the empty window is 'no-sample'", () => {
    const r = row(
      buildReliabilityLens([{ agentId: "a1", snapshot: domainSnapshot(HONOURED) }]).rows,
      0,
    );
    expect(r).toMatchObject({
      toolErrors: 0,
      toolTotal: 9521,
      toolRefusal: null,
      totalTokens: 11124,
      costN: 7,
      costRefusal: null,
    });
    const empty = domainSnapshot(HONOURED, {
      tool_validity: { total: 0, allowed: 0, denied: 0, errored: 0 },
      cost: { n_turns: 0, total_tokens: 0, mean_tokens: 0 },
    });
    const q = row(buildReliabilityLens([{ agentId: "quiet", snapshot: empty }]).rows, 0);
    expect(q).toMatchObject({
      toolErrors: null,
      toolRefusal: "no-sample",
      totalTokens: null,
      costRefusal: "no-sample",
    });
  });

  it("reliability: an org-wide report refuses the cells, whatever the data says", () => {
    const orgWide = domainSnapshot({ ...HONOURED, org_wide: true });
    const r = row(buildReliabilityLens([{ agentId: "a1", snapshot: orgWide }]).rows, 0);
    expect(r.toolErrors).toBeNull();
    expect(r.toolRefusal).toBe("org-wide");
    expect(r.totalTokens).toBeNull();
    expect(r.costRefusal).toBe("org-wide");
  });

  it("observability: honoured values come through; the empty window is 'no-sample'", () => {
    const r = row(
      buildObservabilityLens([{ agentId: "a1", snapshot: domainSnapshot(HONOURED) }]).rows,
      0,
    );
    expect(r).toMatchObject({
      anomalous: 0,
      sessions: 7,
      anomaliesRefusal: null,
      violations: 0,
      calls: 9521,
      conformanceRefusal: null,
    });
    const empty = domainSnapshot(HONOURED, {
      anomalies: { n_anomalous: 0, n_sessions: 0, sessions: [] },
      conformance: { conformance_rate: 1.0, n_calls: 0, n_violations: 0, violations: [] },
    });
    const q = row(buildObservabilityLens([{ agentId: "quiet", snapshot: empty }]).rows, 0);
    expect(q).toMatchObject({
      anomalous: null,
      anomaliesRefusal: "no-sample",
      violations: null,
      conformanceRefusal: "no-sample",
    });
  });

  it("observability: an org-wide report refuses the cells, whatever the data says", () => {
    // THE ratchet the mutation test targets on this lens: bypass the gate on `anomalies`
    // and this goes red — the data is present, the report refuses the slice.
    const orgWide = domainSnapshot({ ...HONOURED, org_wide: true });
    const r = row(buildObservabilityLens([{ agentId: "a1", snapshot: orgWide }]).rows, 0);
    expect(r.anomalous).toBeNull();
    expect(r.anomaliesRefusal).toBe("org-wide");
    expect(r.violations).toBeNull();
    expect(r.conformanceRefusal).toBe("org-wide");
  });

  it("proof: the SAME gated rows as compliance, under the proof kind — no second door", () => {
    const snapshots = [{ agentId: "a1", snapshot: domainSnapshot(HONOURED) }];
    const proof = buildProofLens(snapshots);
    expect(proof.kind).toBe("proof");
    expect(proof.rows).toEqual(buildComplianceLens(snapshots).rows);
    // And it refuses the same way: an org-wide report empties the cells, data or not.
    const orgWide = buildProofLens([
      { agentId: "a1", snapshot: domainSnapshot({ ...HONOURED, org_wide: true }) },
    ]);
    expect(row(orgWide.rows, 0)).toMatchObject({
      governedActs: null,
      governedRefusal: "org-wide",
      ledgerEntries: null,
      ledgerRefusal: "org-wide",
    });
  });

  it("observability: one signal's refusal empties ITS cells only — never its neighbours'", () => {
    const mixed: OverviewSnapshot = {
      signals: {
        anomalies: {
          data: DOMAIN_DATA.anomalies,
          report: { ...HONOURED, honoured: ["time"], ignored: ["agent"] },
        },
        conformance: { data: DOMAIN_DATA.conformance, report: HONOURED },
      },
    };
    const r = row(buildObservabilityLens([{ agentId: "a1", snapshot: mixed }]).rows, 0);
    expect(r.anomaliesRefusal).toBe("not-honoured");
    expect(r.anomalous).toBeNull();
    expect(r.violations).toBe(0);
    expect(r.calls).toBe(9521);
  });
});

describe("the focused signal (?signal=) is what reaches the lens", () => {
  it("reads the focus from the URL, and treats an empty one as 'no focus'", () => {
    expect(readSignalFocus({ signal: "firewall" })).toBe("firewall");
    expect(readSignalFocus(new URLSearchParams("signal=refusal&agent=all"))).toBe("refusal");
    expect(readSignalFocus({})).toBeUndefined();
    expect(readSignalFocus({ signal: "  " })).toBeUndefined();
  });

  it("maps the UI row key to the id the CAPABILITY REGISTRY knows it by", () => {
    // The registry says `pii_leak`; the signals table's row key is `piiLeak`. One mapping,
    // in one place — the rail's explanation and the table's masking must agree by construction.
    expect(registryIdFor("piiLeak")).toBe("pii_leak");
    expect(registryIdFor("firewall")).toBe("firewall");
  });

  it("focusing an org-wide signal masks the table — the state is REACHABLE from the UI", () => {
    // Selecting the row in the registry sets ?signal=<id>; the server re-plans the lens.
    // Without this the masked lens would exist and never render, which is a decoration.
    for (const uiKey of ["firewall", "refusal"]) {
      const id = registryIdFor(uiKey);
      expect(isOrgWide(id)).toBe(true);
      expect(planLens(snapshot(HONOURED), id)).toEqual({ kind: "masked", signalId: id });
    }
  });

  it("focusing a per-agent signal we cannot read per agent falls back to quality, never to a guess", () => {
    // `toxicity` IS per-agent, but this lens has no per-agent reader for it. We show what we
    // can prove (the quality lens) rather than dress the SLO's numbers up as toxicity's.
    expect(isOrgWide("toxicity")).toBe(false);
    expect(planLens(snapshot(HONOURED), "toxicity")).toEqual({ kind: "quality" });
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

  it("n = 0 is 'no sample', never a fabricated 0 % — and it is NOT a refusal", () => {
    // Three of the six live agents have zero turns. A measured emptiness and an unprovable
    // slice are both dashes on screen, but they are different facts: the read SUCCEEDED here.
    // Collapsing them would make the honest case look like the broken one.
    const empty = snapshot(HONOURED, { ...SLO_DATA, n: 0, n_bad: 0, good_rate: 0 });
    const lens = buildAlarmLens("slo", snapshot(HONOURED), [{ agentId: "quiet", snapshot: empty }]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(row(lens.rows, 0)).toMatchObject({
      value: null,
      gapPp: null,
      nBad: null,
      n: 0,
      refusal: "no-sample",
    });
  });

  it("an agent with no turns does not inflate the ∑ of contributions", () => {
    const empty = snapshot(HONOURED, { ...SLO_DATA, n: 0, n_bad: 0, good_rate: 0 });
    const org = snapshot(HONOURED, { ...SLO_DATA, n: 67, n_bad: 19 });
    const lens = buildAlarmLens("slo", org, [
      { agentId: "heavy", snapshot: heavy },
      { agentId: "quiet", snapshot: empty },
    ]);
    if (lens.kind !== "alarm") throw new Error("expected the alarm lens");
    expect(lens.sumNBad).toBe(14); // heavy only — the empty agent contributes nothing, not a 0-row
  });
});

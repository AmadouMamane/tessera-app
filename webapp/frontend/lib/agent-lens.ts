/**
 * The lens over the per-agent breakdown table (Qualité IA) — the backend honesty
 * doctrine ported to the front.
 *
 * The monitoring columns (volume / latency / handoffs) answer a monitoring question;
 * on a quality page whose banner names a breached signal, the table must answer THAT
 * signal. This module decides which lens the page needs (`planLens`) and builds its
 * rows, with two invariants the tests ratchet:
 *
 * 1. **Every per-agent number passes through `selectHonouredSignal`.** A value the
 *    signal's own scope report does not declare honoured for `"agent"` is
 *    unrepresentable in a lens row — the cell stays `null` and carries its refusal.
 * 2. **An org-wide signal never yields a per-agent table.** The lens comes back
 *    `masked` (from the `capabilities.py` mirror, `signal-registry.ts`) before any
 *    per-agent read happens; the "Fiche signal" rail says why the table is hidden.
 *
 * Pure module (no React/Next/fetch) — the server loader in `lib/server/agent-lens.ts`
 * fetches the snapshots, this file only refuses or derives.
 */

import { z } from "zod";

import { SLOReportSchema } from "./api/schemas";
import {
  type OverviewSnapshot,
  type ScopedRefusal,
  selectHonouredSignal,
  selectSignal,
} from "./overview-snapshot";
import { isOrgWide } from "./signal-registry";

/** Raw per-turn score rows (`scores` signal) — only the fields the lens reads. */
const SnapshotScoresSchema = z.object({
  scores: z.array(z.object({ metric: z.string(), score: z.number() })),
});

/** One agent's snapshot, as the server loader hands it over. */
export interface AgentSnapshot {
  agentId: string;
  snapshot: OverviewSnapshot | undefined;
}

/**
 * Why a cell is empty. A refusal means the value could not be PROVEN; `"no-sample"` means it
 * was measured and there was nothing on the window — an agent with zero turns contributes zero
 * bad turns, which is a fact, not a hole. The two must not read alike: three of the six live
 * agents have n = 0, and rendering their emptiness identically to a refused read would make the
 * honest case look like the broken one.
 */
export type CellEmpty = ScopedRefusal | "no-sample";

export interface AlarmLensRow {
  agentId: string;
  /** The breached signal's own value for this agent (rate 0..1), when honoured. */
  value: number | null;
  /** Distance to the SLO target in percentage points (negative = below target). */
  gapPp: number | null;
  /** This agent's contribution to the breach: its own bad turns on the window. */
  nBad: number | null;
  /** This agent's sample size on the window. */
  n: number | null;
  /** Why the cells are empty, when they are — never a silent dash. */
  refusal: CellEmpty | null;
}

export interface AlarmLens {
  kind: "alarm";
  signalId: string;
  /** The breached metric as the SLO report names it (e.g. "faithfulness"). */
  metric: string | null;
  target: number | null;
  orgNBad: number | null;
  orgN: number | null;
  /**
   * Sum of the per-agent contributions. Displayed WITH its reconciliation against
   * `orgNBad`: a handed-off journey touches two agents but counts once in the org,
   * so equality would be a coincidence, not a proof — a gap is stated, never smoothed.
   */
  sumNBad: number | null;
  /** Sorted by contribution, descending; agents with no honoured value last. */
  rows: AlarmLensRow[];
}

export interface QualityLensRow {
  agentId: string;
  faithfulness: number | null;
  faithfulnessRefusal: CellEmpty | null;
  hallucination: number | null;
  hallucinationRefusal: CellEmpty | null;
}

export interface QualityLens {
  kind: "quality";
  rows: QualityLensRow[];
}

/** An org-wide signal cannot name a per-agent culprit — the table is masked, with the why. */
export interface MaskedLens {
  kind: "masked";
  signalId: string;
}

/** The historical columns (volume / escalation / latency / handoffs) — the default. */
export interface MonitoringLens {
  kind: "monitoring";
}

export type BreakdownLens = MonitoringLens | AlarmLens | QualityLens | MaskedLens;

export type LensPlan =
  | { kind: "alarm"; signalId: string }
  | { kind: "quality" }
  | { kind: "masked"; signalId: string };

/** The alarm signal this lens can actually READ per agent. Anything else is not answerable. */
export const ALARM_SIGNAL = "slo";

/**
 * Decide from the org snapshot which lens the page needs — before any per-agent fan-out.
 *
 * `signalId` is the signal in focus: the page's alarm source (the SLO hero) by default, or the
 * one the operator selected in the registry (`?signal=`). Three outcomes, in this order:
 *
 * 1. **org-wide** (`refusal`, `firewall`, `audit_integrity`, … — the AGENT dimension is absent
 *    from its capability): masked, right here, before any per-agent read is even attempted. A
 *    signal with no per-agent substrate must not be handed a per-agent table.
 * 2. **the alarm**, when the SLO is breaching and the focused signal is the one we can read per
 *    agent: the table answers it.
 * 3. **quality** otherwise — including a per-agent signal we have no per-agent reader for. We
 *    fall back to what we CAN prove rather than fabricate columns for a signal we cannot slice.
 */
export function planLens(
  orgSnapshot: OverviewSnapshot | undefined,
  signalId = ALARM_SIGNAL,
): LensPlan {
  if (isOrgWide(signalId)) return { kind: "masked", signalId };
  const slo = selectSignal(orgSnapshot, ALARM_SIGNAL, SLOReportSchema);
  if (slo?.breaching && signalId === ALARM_SIGNAL) return { kind: "alarm", signalId };
  return { kind: "quality" };
}

/**
 * Build the alarm lens rows from per-agent snapshots. Re-guards org-wide (belt and
 * braces with `planLens`): displaying a per-agent value for an org-wide signal is a
 * red, not a rendering choice.
 */
export function buildAlarmLens(
  signalId: string,
  orgSnapshot: OverviewSnapshot | undefined,
  agentSnapshots: readonly AgentSnapshot[],
): AlarmLens | MaskedLens {
  if (isOrgWide(signalId)) return { kind: "masked", signalId };
  const org = selectSignal(orgSnapshot, "slo", SLOReportSchema);
  const rows: AlarmLensRow[] = agentSnapshots
    .map(({ agentId, snapshot }): AlarmLensRow => {
      const sel = selectHonouredSignal(snapshot, "slo", SLOReportSchema, "agent");
      if (!sel.ok) {
        return { agentId, value: null, gapPp: null, nBad: null, n: null, refusal: sel.refusal };
      }
      // n = 0 is "no sample", not "0 % bad" — honest-empty, never a fabricated zero. It is
      // NOT a refusal: the read succeeded and found nothing, and the cell says which.
      if (sel.data.n === 0) {
        return { agentId, value: null, gapPp: null, nBad: null, n: 0, refusal: "no-sample" };
      }
      return {
        agentId,
        value: sel.data.good_rate,
        gapPp: (sel.data.good_rate - sel.data.target) * 100,
        nBad: sel.data.n_bad,
        n: sel.data.n,
        refusal: null,
      };
    })
    .sort((a, b) => (b.nBad ?? -1) - (a.nBad ?? -1));
  const contributions = rows.filter((r) => r.nBad !== null).map((r) => r.nBad ?? 0);
  return {
    kind: "alarm",
    signalId,
    metric: org?.metric ?? null,
    target: org?.target ?? null,
    orgNBad: org?.n_bad ?? null,
    orgN: org?.n ?? null,
    sumNBad: contributions.length > 0 ? contributions.reduce((s, v) => s + v, 0) : null,
    rows,
  };
}

/** Build the quality lens rows (no alarm): per-agent faithfulness + hallucination. */
export function buildQualityLens(agentSnapshots: readonly AgentSnapshot[]): QualityLens {
  const rows: QualityLensRow[] = agentSnapshots.map(({ agentId, snapshot }): QualityLensRow => {
    const slo = selectHonouredSignal(snapshot, "slo", SLOReportSchema, "agent");
    const scores = selectHonouredSignal(snapshot, "scores", SnapshotScoresSchema, "agent");
    let hallucination: number | null = null;
    let hallucinationEmpty: CellEmpty | null = scores.ok ? null : scores.refusal;
    if (scores.ok) {
      const values = scores.data.scores
        .filter((s) => s.metric === "hallucination")
        .map((s) => s.score);
      if (values.length === 0) {
        hallucinationEmpty = "no-sample";
      } else {
        hallucination = values.reduce((sum, v) => sum + v, 0) / values.length;
      }
    }
    const noTurns = slo.ok && slo.data.n === 0;
    return {
      agentId,
      faithfulness: slo.ok && slo.data.n > 0 ? slo.data.good_rate : null,
      faithfulnessRefusal: slo.ok ? (noTurns ? "no-sample" : null) : slo.refusal,
      hallucination,
      hallucinationRefusal: hallucinationEmpty,
    };
  });
  return { kind: "quality", rows };
}

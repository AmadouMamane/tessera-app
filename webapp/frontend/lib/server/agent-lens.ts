import "server-only";

import {
  type AgentSnapshot,
  type BreakdownLens,
  buildAlarmLens,
  buildQualityLens,
  planLens,
} from "@/lib/agent-lens";
import { type Fleet, OverviewSnapshotSchema } from "@/lib/api/schemas";
import type { OverviewSnapshot } from "@/lib/overview-snapshot";

import { backendHeaders, backendUrl } from "./backend";

/**
 * Server-side lens loader for the Qualité IA breakdown table.
 *
 * One org read decides the lens (breach → alarm; quiet → quality; org-wide breach →
 * masked, no fan-out at all), then one snapshot per fleet agent. The snapshot endpoint
 * is cached + single-flighted backend-side (ADR 0015 §Performance), so the fan-out is
 * N cache hits after the first render — measured before shipping, see the commit.
 *
 * Any failed read yields `undefined` and the lens rows render their honest refusal —
 * never a fabricated value, never a blank page.
 */
async function fetchSnapshot(params: {
  agent?: string;
  signals: string;
}): Promise<OverviewSnapshot | undefined> {
  try {
    const qs = new URLSearchParams();
    if (params.agent) qs.set("agent", params.agent);
    qs.set("signals", params.signals);
    const res = await fetch(`${backendUrl()}/observability/snapshot?${qs.toString()}`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return undefined;
    return OverviewSnapshotSchema.parse(await res.json());
  } catch {
    return undefined;
  }
}

export async function loadBreakdownLens(
  fleet: Fleet | null,
  signalId?: string,
): Promise<BreakdownLens> {
  const agents = fleet?.agents ?? [];
  if (agents.length === 0) return { kind: "monitoring" };
  const org = await fetchSnapshot({ signals: "slo" });
  const plan = planLens(org, signalId);
  // An org-wide signal is settled by its declared capability alone: no per-agent fan-out at all.
  if (plan.kind === "masked") return { kind: "masked", signalId: plan.signalId };
  const signals = plan.kind === "alarm" ? "slo" : "slo,scores";
  const perAgent: AgentSnapshot[] = await Promise.all(
    agents.map(async (a) => ({
      agentId: a.id,
      snapshot: await fetchSnapshot({ agent: a.id, signals }),
    })),
  );
  return plan.kind === "alarm"
    ? buildAlarmLens(plan.signalId, org, perAgent)
    : buildQualityLens(perAgent);
}

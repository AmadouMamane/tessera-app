import "server-only";

import { backendHeaders, backendUrl } from "./backend";
import { loadFleet } from "./fleet";

/**
 * Public-safe launcher signal (ADR 0009 boundary).
 *
 * The demo launcher is a PUBLIC page, so it may only surface AGGREGATE,
 * showcase-safe quality signals — the fleet rollup (agent count, per-agent health
 * + non-regression GATE verdict) and the last eval timestamp. It never exposes the
 * operator-gated detail (audit trail, per-CASE eval failure reasons, incidents,
 * budget). Returns `null` on any failure so the launcher renders an honest empty
 * state ("indisponible"), never a fabricated number or a fake "live" pulse.
 */
export type AgentHealth = "good" | "warn" | "crit" | "unknown";

export interface LauncherAgentSignal {
  name: string;
  health: AgentHealth;
  gatePassed: boolean | null;
  gateLabel: string | null;
}

export interface LauncherSignal {
  agentsCount: number;
  passedAgents: number;
  agentsWithRelease: number;
  gateVerdict: "pass" | "blocked" | "unknown";
  // Aggregate, public-safe case pass rate (0..1): blocking eval failures over
  // total executions across the fleet. It tells the honest nuance — most cases
  // pass even while the release gate stays blocked on the security baseline. It
  // is a rollup number (no per-case reasons), so it stays inside the ADR 0009
  // showcase boundary. `null` when no agent has run an eval.
  casesPassRate: number | null;
  lastEvalAt: string | null;
  agents: LauncherAgentSignal[];
}

function asHealth(value: string): AgentHealth {
  return value === "good" || value === "warn" || value === "crit" ? value : "unknown";
}

/** Latest online-eval score timestamp (real telemetry) — the "last eval" date. */
async function latestEvalAt(): Promise<string | null> {
  try {
    const res = await fetch(`${backendUrl()}/observability/scores`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { scores?: Array<{ scored_at?: unknown }> };
    const stamps = (data.scores ?? [])
      .map((s) => s.scored_at)
      .filter((x): x is string => typeof x === "string");
    if (stamps.length === 0) return null;
    return stamps.reduce((a, b) => (a > b ? a : b));
  } catch {
    return null;
  }
}

export async function loadLauncherSignal(): Promise<LauncherSignal | null> {
  const fleet = await loadFleet();
  if (!fleet?.available || !fleet.agents || fleet.agents.length === 0) return null;

  const agents: LauncherAgentSignal[] = fleet.agents.map((a) => ({
    name: a.name,
    health: asHealth(a.health),
    gatePassed: a.release ? a.release.passed : null,
    gateLabel: a.release?.verdict_label ?? null,
  }));
  const withRelease = agents.filter((a) => a.gatePassed !== null);
  const passedAgents = withRelease.filter((a) => a.gatePassed === true).length;
  const gateVerdict: LauncherSignal["gateVerdict"] =
    withRelease.length === 0 ? "unknown" : passedAgents === withRelease.length ? "pass" : "blocked";

  // Real aggregate from the fleet release rollup: total eval executions and the
  // count that blocks the gate (socle baseline + tier-1). Pass rate is the share
  // that did NOT block — never fabricated, never per-case.
  let totalExecutions = 0;
  let totalBlocking = 0;
  for (const a of fleet.agents) {
    if (!a.release) continue;
    totalExecutions += a.release.executions;
    totalBlocking += a.release.blocking_socle + a.release.blocking_t1;
  }
  const casesPassRate =
    totalExecutions > 0
      ? Math.max(0, Math.min(1, (totalExecutions - totalBlocking) / totalExecutions))
      : null;

  return {
    agentsCount: agents.length,
    passedAgents,
    agentsWithRelease: withRelease.length,
    gateVerdict,
    casesPassRate,
    lastEvalAt: await latestEvalAt(),
    agents,
  };
}

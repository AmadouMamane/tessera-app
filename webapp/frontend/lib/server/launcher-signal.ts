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
  // Per-agent STRICT pass rate (0..1): passed executions over total executions of
  // THIS agent's own reference run. A real, public-safe rollup that maps to a
  // single agent — the verdict + this rate are showcase-safe; WHICH case failed
  // (the failure category) stays operator-only (ADR 0009). `null` if no run.
  strictPassRate: number | null;
}

export interface LauncherSignal {
  agentsCount: number;
  // The only legitimate fleet-level number: how many agents are releasable
  // (gate green) out of those with a run. No blended fleet "%" — a rate belongs
  // to one agent, never to the fleet.
  passedAgents: number;
  agentsWithRelease: number;
  gateVerdict: "pass" | "blocked" | "unknown";
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

  const agents: LauncherAgentSignal[] = fleet.agents.map((a) => {
    // Strict pass rate of THIS agent's own run: passed executions / total
    // executions. Real, maps to exactly one agent — never a fleet blend.
    const exec = a.release?.executions ?? 0;
    const passed = a.release?.passed_exec ?? null;
    const strictPassRate =
      a.release && passed !== null && exec > 0 ? Math.max(0, Math.min(1, passed / exec)) : null;
    return {
      name: a.name,
      health: asHealth(a.health),
      gatePassed: a.release ? a.release.passed : null,
      gateLabel: a.release?.verdict_label ?? null,
      strictPassRate,
    };
  });
  const withRelease = agents.filter((a) => a.gatePassed !== null);
  const passedAgents = withRelease.filter((a) => a.gatePassed === true).length;
  const gateVerdict: LauncherSignal["gateVerdict"] =
    withRelease.length === 0 ? "unknown" : passedAgents === withRelease.length ? "pass" : "blocked";

  return {
    agentsCount: agents.length,
    passedAgents,
    agentsWithRelease: withRelease.length,
    gateVerdict,
    lastEvalAt: await latestEvalAt(),
    agents,
  };
}

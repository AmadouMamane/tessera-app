import "server-only";

import { AuditIntegritySchema, GuardActivitySchema } from "@/lib/api/schemas";

import { backendHeaders, backendUrl } from "./backend";
import { loadComprendreFacts } from "./comprendre";
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
  // Pass rate (0..1) EXACTLY as the cockpit/reports show it: summary passed/total
  // of THIS agent's own run, against its OWN domain set. NOT comparable across
  // agents (different sets, staggered runs) — labelled "contre son propre set".
  // `passed`/`total` are surfaced too so every rate shows its verifiable fraction.
  passRate: number | null;
  passed: number | null;
  total: number | null;
  // Provenance so the staggered, independent nature is visible — never a single
  // hidden fleet snapshot. (ADR 0010.)
  runAt: string | null;
  catalogueVersion: string | null;
  // True when this run was scored against a SUPERSEDED catalogue → re-eval needed.
  verdictStale: boolean;
  // Shared security floor — the ONLY legitimate cross-agent comparator (same
  // cases for every agent). `null` when not run.
  soclePassed: number | null;
  socleTotal: number | null;
}

export interface LauncherSignal {
  agentsCount: number;
  // The only legitimate fleet-level number: how many agents are releasable
  // (gate green) out of those with a run. No blended fleet "%" — a rate belongs
  // to one agent, never to the fleet.
  passedAgents: number;
  agentsWithRelease: number;
  // Exact ready/review buckets from the same backend aggregate `/comprendre` renders.
  // The public /eval pillar consumes this object, never a second frontend calculation.
  evaluationBuckets: { ready: number; review: number } | null;
  gateVerdict: "pass" | "blocked" | "unknown";
  agents: LauncherAgentSignal[];
  // Real, fleet-wide audit-chain content-integrity verdict (tamper-evidence),
  // read from /audit/integrity and surfaced ONLY as an aggregate boolean
  // (ADR 0009 showcase-safe): the chain re-derives (true), a proven break
  // (false), or unavailable (null → the launcher shows an honest "vérification
  // indisponible", never a fabricated "vérifiée"). NEVER inferred from the mere
  // existence of audit entries.
  integrityVerified: boolean | null;
  // Full opposability verdict: only `scelle_opposable` earns the public
  // “registre infalsifiable” state (ADR 0042). Null means the check is unreachable.
  opposabilityBadge:
    | "non_scelle"
    | "scelle_opposable"
    | "scelle_non_qualifie"
    | "integrite_partielle"
    | null;
  // Guard activity since local midnight — messages checked (transcript turns,
  // ADR 0040) and denials recorded (audit trail), each from its own witness.
  // `null` → the band's SECURE column renders "compteurs indisponibles".
  guardActivity: { checkedToday: number; blockedToday: number } | null;
  // Server instant this aggregate was assembled — the freshness the band's
  // "temps réel" claim rests on (the client re-fetches and shows the age).
  generatedAt: string;
}

function asHealth(value: string): AgentHealth {
  return value === "good" || value === "warn" || value === "crit" ? value : "unknown";
}

/**
 * Fleet-wide audit-chain content-integrity verdict (tamper-evidence), or `null`
 * when the check is unreachable — never a fabricated "verified". The launcher
 * surfaces ONLY this aggregate boolean (ADR 0009), never the audit trail itself.
 */
async function loadIntegrityVerdict(): Promise<{
  verified: boolean | null;
  badge: LauncherSignal["opposabilityBadge"];
}> {
  try {
    const res = await fetch(`${backendUrl()}/audit/integrity`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return { verified: null, badge: null };
    const integrity = AuditIntegritySchema.parse(await res.json());
    return { verified: integrity.verified, badge: integrity.badge };
  } catch {
    return { verified: null, badge: null };
  }
}

/**
 * Guard activity since local midnight (checked / blocked message counts), or
 * `null` when the read is unreachable or a witness is down — never a fabricated
 * zero. Aggregate-only, like everything else on this public surface.
 */
async function loadGuardActivity(): Promise<LauncherSignal["guardActivity"]> {
  try {
    const res = await fetch(`${backendUrl()}/observability/guard-activity`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return null;
    const parsed = GuardActivitySchema.parse(await res.json());
    if (!parsed.available || parsed.checked_today === undefined) return null;
    return {
      checkedToday: parsed.checked_today,
      blockedToday: parsed.blocked_today ?? 0,
    };
  } catch {
    return null;
  }
}

export async function loadLauncherSignal(): Promise<LauncherSignal | null> {
  const [fleet, integrity, guardActivity, comprendre] = await Promise.all([
    loadFleet(),
    loadIntegrityVerdict(),
    loadGuardActivity(),
    loadComprendreFacts(),
  ]);
  if (!fleet?.available || !fleet.agents || fleet.agents.length === 0) return null;

  const agents: LauncherAgentSignal[] = fleet.agents.map((a) => {
    const rel = a.release ?? null;
    // Pass rate as the report/cockpit show it: summary passed / total of THIS
    // run (its own set). Real, single-agent — never a fleet blend, never the
    // execution grain. `null` when the summary total is unavailable.
    const total = rel?.summary_total ?? 0;
    const passed = rel?.summary_passed ?? null;
    const passRate =
      rel && passed !== null && total > 0 ? Math.max(0, Math.min(1, passed / total)) : null;
    return {
      name: a.name,
      health: asHealth(a.health),
      gatePassed: rel ? rel.passed : null,
      gateLabel: rel?.verdict_label ?? null,
      passRate,
      passed: rel?.summary_passed ?? null,
      total: rel?.summary_total ?? null,
      runAt: rel?.run_at ?? null,
      catalogueVersion: rel?.catalogue_version ?? null,
      verdictStale: rel?.verdict_stale ?? false,
      soclePassed: rel?.socle_passed ?? null,
      socleTotal: rel?.socle_total ?? null,
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
    evaluationBuckets:
      comprendre.available &&
      comprendre.evaluations.ready_agents !== null &&
      comprendre.evaluations.review_agents !== null
        ? {
            ready: comprendre.evaluations.ready_agents,
            review: comprendre.evaluations.review_agents,
          }
        : null,
    gateVerdict,
    agents,
    integrityVerified: integrity.verified,
    opposabilityBadge: integrity.badge,
    guardActivity,
    generatedAt: new Date().toISOString(),
  };
}

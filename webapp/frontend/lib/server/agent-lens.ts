import "server-only";

import { cache } from "react";

import {
  type AgentSnapshot,
  type BreakdownLens,
  buildAlarmLens,
  buildComplianceLens,
  buildObservabilityLens,
  buildProofLens,
  buildQualityLens,
  buildReliabilityLens,
  buildSecurityLens,
  planLens,
} from "@/lib/agent-lens";
import { type Fleet, FleetSnapshotSchema, OverviewSnapshotSchema } from "@/lib/api/schemas";
import type { OverviewSnapshot } from "@/lib/overview-snapshot";
import { type AgentBreakdownDomain, type DeclaredLensRoute, PAGE_NATURE } from "@/lib/page-nature";

import { backendHeaders, backendUrl } from "./backend";

/**
 * The URL-keyed snapshot read behind `fetchSnapshot`, wrapped in React `cache()`.
 *
 * The per-agent fan-out asks the same `?agent=&signals=` snapshot at most once per
 * render tree — the org `slo` read that decides the plan and any repeated per-agent
 * read collapse to one tunnel round-trip. Keyed on the built URL string (request-scoped,
 * never across renders); outside a render `cache()` is a passthrough, so tests are
 * unaffected. This is on top of the backend's own read-through cache (ADR 0015).
 */
const fetchSnapshotByUrl = cache(async (url: string): Promise<OverviewSnapshot | undefined> => {
  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return undefined;
    return OverviewSnapshotSchema.parse(await res.json());
  } catch {
    return undefined;
  }
});

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
function fetchSnapshot(params: {
  agent?: string;
  signals: string;
}): Promise<OverviewSnapshot | undefined> {
  const qs = new URLSearchParams();
  if (params.agent) qs.set("agent", params.agent);
  qs.set("signals", params.signals);
  return fetchSnapshotByUrl(`${backendUrl()}/observability/snapshot?${qs.toString()}`);
}

/**
 * The URL-keyed bulk fleet-snapshot read behind `fetchFleetSnapshot`, in React `cache()`.
 *
 * Every GOUVERNER breakdown asked one `?agent=<id>` snapshot per fleet agent — N tunnel
 * round-trips whose intermittent tail was the free tunnel serialising them. `/fleet-snapshot`
 * returns them all in ONE round-trip; the backend reuses the SAME per-agent builder, so each
 * slice is byte-identical to the single-agent route it replaces. Keyed on the URL string
 * (request-scoped; an object key would never dedupe); a failed read yields an empty Map, so
 * every agent resolves to `undefined` and renders its honest refusal — same as an outage today.
 */
const fetchFleetSnapshotByUrl = cache(
  async (url: string): Promise<Map<string, OverviewSnapshot>> => {
    try {
      const res = await fetch(url, {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      });
      if (!res.ok) return new Map();
      const parsed = FleetSnapshotSchema.parse(await res.json());
      return new Map(
        parsed.agents.map((a): [string, OverviewSnapshot] => [a.agent_id, a.snapshot]),
      );
    } catch {
      return new Map();
    }
  },
);

/** Fetch every fleet agent's snapshot for `signals` in one round-trip, keyed by agent id. */
function fetchFleetSnapshot(signals: string): Promise<Map<string, OverviewSnapshot>> {
  const qs = new URLSearchParams();
  qs.set("signals", signals);
  return fetchFleetSnapshotByUrl(`${backendUrl()}/observability/fleet-snapshot?${qs.toString()}`);
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
  const snapshots = await fetchFleetSnapshot(signals);
  const perAgent: AgentSnapshot[] = agents.map((a) => ({
    agentId: a.id,
    snapshot: snapshots.get(a.id),
  }));
  return plan.kind === "alarm"
    ? buildAlarmLens(plan.signalId, org, perAgent)
    : buildQualityLens(perAgent);
}

/**
 * The GOUVERNER domains whose pages carry their own per-agent lens — the registry's
 * breakdown domains minus `quality` (which routes through `loadBreakdownLens`, the
 * dynamic alarm/quality/masked plan). Tied to `page-nature.ts` so a NEW breakdown domain
 * declared there cannot exist without a signal fan-out here: `DOMAIN_SIGNALS` stops
 * compiling until the domain is served.
 */
export type LensDomain = Exclude<AgentBreakdownDomain, "quality">;

/**
 * The per-agent signals each domain page fans out for — ONLY signals measured to answer
 * `honoured: ["agent"]` (see `lib/agent-lens.ts` schemas). A domain fact the spine holds
 * org-wide (guard efficacy, injection bypass, latency p95) is deliberately absent: it is
 * not depositable per agent, so it does not become a column. `improvement` reuses the
 * QUALITY lens (product decision, 2026-07-15): no per-agent improvement signal exists
 * (`regression_risk` is org-wide), and the per-agent regression facts already live in the
 * release payload the quality columns render — nothing invented.
 */
const DOMAIN_SIGNALS: Record<LensDomain, string> = {
  security: "pii_leak,toxicity,tool_validity",
  compliance: "governance,audit_count",
  reliability: "tool_validity,cost",
  improvement: "slo,scores",
  // Measured 2026-07-15 (`?agent=<id>&signals=…`, 6/6 agents `honoured: ["agent"]`).
  // `traces` is deliberately absent: declared per-agent in capabilities.py but with no
  // registered read — a declared capability with no serve is not a substrate.
  observability: "anomalies,conformance",
  // The proof facts per agent ARE the compliance counts (same signals, same builder rows);
  // audit-chain INTEGRITY is org-wide by construction and deliberately not fanned out.
  proof: "governance,audit_count",
};

/**
 * Server-side lens loader for the domain pages (Sécurité & Privacy, Conformité,
 * Fiabilité & coût): one snapshot per fleet agent, no org plan step — the domain is the
 * page's own question, not an alarm decision. Same cached + single-flighted endpoint as
 * `loadBreakdownLens`; any failed read yields honest refusal cells, never a blank page.
 */
export async function loadDomainLens(
  fleet: Fleet | null,
  domain: LensDomain,
): Promise<BreakdownLens> {
  const agents = fleet?.agents ?? [];
  if (agents.length === 0) return { kind: "monitoring" };
  const snapshots = await fetchFleetSnapshot(DOMAIN_SIGNALS[domain]);
  const perAgent: AgentSnapshot[] = agents.map((a) => ({
    agentId: a.id,
    snapshot: snapshots.get(a.id),
  }));
  switch (domain) {
    case "security":
      return buildSecurityLens(perAgent);
    case "compliance":
      return buildComplianceLens(perAgent);
    case "reliability":
      return buildReliabilityLens(perAgent);
    case "improvement":
      return buildQualityLens(perAgent);
    case "observability":
      return buildObservabilityLens(perAgent);
    case "proof":
      return buildProofLens(perAgent);
  }
}

/**
 * Load the lens a page DECLARES — the single door between the page-nature registry and
 * the rendered columns. The page hands over its own route; the domain comes from
 * `PAGE_NATURE`, never from the caller, so a page declared `lens:security` structurally
 * cannot render another domain's columns. The route parameter only accepts routes whose
 * declared nature is an AgentBreakdown lens (`DeclaredLensRoute`): calling this from an
 * org-wide, monitoring or bespoke page is a compile error, not a runtime fallback.
 */
export async function loadDeclaredLens(
  route: DeclaredLensRoute,
  fleet: Fleet | null,
  opts: { signalId?: string } = {},
): Promise<BreakdownLens> {
  const { domain } = PAGE_NATURE[route];
  return domain === "quality"
    ? loadBreakdownLens(fleet, opts.signalId)
    : loadDomainLens(fleet, domain);
}

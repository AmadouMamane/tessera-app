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
import {
  type Fleet,
  FleetBatchSchema,
  FleetSchema,
  FleetSnapshotSchema,
  OverviewSnapshotSchema,
} from "@/lib/api/schemas";
import type { OverviewSnapshot } from "@/lib/overview-snapshot";
import { type AgentBreakdownDomain, type DeclaredLensRoute, PAGE_NATURE } from "@/lib/page-nature";

import { backendHeaders, backendUrl } from "./backend";
import { type SearchParams, fleetQuery } from "./fleet";

/**
 * The URL-keyed bulk fleet-snapshot read behind `fetchFleetSnapshot`, in React `cache()`.
 *
 * Every GOUVERNER breakdown asked one `?agent=<id>` snapshot per fleet agent — N tunnel
 * round-trips whose intermittent tail was the free tunnel serialising them. `/fleet-snapshot`
 * returns them all in ONE round-trip; the backend reuses the SAME per-agent builder, so each
 * slice is byte-identical to the single-agent route it replaces. Keyed on the URL string
 * (request-scoped; an object key would never dedupe); a failed read yields an empty Map, so
 * every agent resolves to `undefined` and renders its honest refusal — same as an outage today.
 *
 * This is now the QUALITY page's fan-out only: a domain page gets the same per-agent slices, from
 * the same backend route, inside the coalesced read below — it has no plan step to wait for, so
 * its fan-out travels with its rollup instead of after it.
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

/**
 * Fetch every fleet agent's snapshot for `signals` in one round-trip, keyed by agent id.
 *
 * `window` is the SAME period/anchor pair the fleet rollup beside these rows was read under
 * (operator decision, 2026-08-26): one card, one clock. Until then this fan-out sent neither,
 * and an absent window deliberately means all history — so the per-agent rows sat on lifetime
 * values under a period rail every neighbouring figure obeyed. Omitting both (the caller passed
 * no search params) keeps that all-history contract.
 */
function fetchFleetSnapshot(
  signals: string,
  window: { days: string | null; at: string | null },
): Promise<Map<string, OverviewSnapshot>> {
  const qs = new URLSearchParams();
  qs.set("signals", signals);
  if (window.days) qs.set("days", window.days);
  if (window.at) qs.set("at", window.at);
  return fetchFleetSnapshotByUrl(`${backendUrl()}/observability/fleet-snapshot?${qs.toString()}`);
}

/** The fleet-wide reads a breakdown needs, each half parsed by its own route's schema. */
interface FleetReads {
  fleet: Fleet | null;
  /** Per-agent snapshots, keyed by agent id — empty unless `signals` was asked for. */
  snapshots: Map<string, OverviewSnapshot>;
  /** The org-wide snapshot — `undefined` unless `org_signals` was asked for. */
  org: OverviewSnapshot | undefined;
}

/** Every half refused: what a failed coalesced read resolves to (never a fabricated value). */
const NO_FLEET_READS: FleetReads = { fleet: null, snapshots: new Map(), org: undefined };

/** Parse one half with the very schema its standalone route used; a bad half refuses alone. */
const parseFleetHalf = (raw: unknown): Fleet | null => {
  const parsed = FleetSchema.safeParse(raw);
  return parsed.success ? parsed.data : null;
};

const parseSnapshotHalf = (raw: unknown): Map<string, OverviewSnapshot> => {
  const parsed = FleetSnapshotSchema.safeParse(raw);
  if (!parsed.success) return new Map();
  return new Map(
    parsed.data.agents.map((a): [string, OverviewSnapshot] => [a.agent_id, a.snapshot]),
  );
};

const parseOrgHalf = (raw: unknown): OverviewSnapshot | undefined => {
  const parsed = OverviewSnapshotSchema.safeParse(raw);
  return parsed.success ? parsed.data : undefined;
};

/**
 * The URL-keyed COALESCED read behind every breakdown, in React `cache()`.
 *
 * The fleet rollup is INDEPENDENT of the snapshot read that accompanies it — a domain page's
 * fan-out asks for its declared domain's signals, the quality page's org read asks for `slo`,
 * neither derived from the rollup — yet they were awaited in series, and each await is a whole
 * tunnel round-trip when the front runs on Cloud Run and the agent on-prem.
 * `/observability/fleet-batch` returns them together, computed concurrently backend-side by the
 * SAME handlers, so each half is byte-identical to the route it replaces (pinned by
 * `tests/unit/test_fleet_batch_parity.py`).
 *
 * Each half is parsed on its own, so the honest-empties stay independent exactly as they were:
 * an unavailable rollup does not empty the snapshots, and an unreadable snapshot half yields an
 * empty Map — every agent resolves to `undefined` and renders its refusal cell, same as an
 * outage today. Keyed on the URL string (request-scoped, never across renders); outside a render
 * `cache()` is a passthrough.
 */
const fetchFleetBatchByUrl = cache(async (url: string): Promise<FleetReads> => {
  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return NO_FLEET_READS;
    const body = FleetBatchSchema.parse(await res.json());
    return {
      fleet: parseFleetHalf(body.fleet),
      snapshots: parseSnapshotHalf(body.fleet_snapshot),
      org: parseOrgHalf(body.snapshot),
    };
  } catch {
    return NO_FLEET_READS;
  }
});

/**
 * Server-side loader for the Qualité IA breakdown: the fleet rollup + the org read that decides
 * the lens, in ONE backend read, then the per-agent fan-out that read chose.
 *
 * The org read decides the plan (breach → alarm columns; quiet → quality columns; org-wide
 * breach → masked, no fan-out at all) and therefore the SIGNALS the fan-out asks for. That is a
 * real dependency, so the fan-out cannot travel with it — coalescing all three would mean
 * fetching signals the plan may not want, or none at all. But the rollup and the org read do NOT
 * depend on each other, so those two travel together: 3 round-trips become 2, and 1 when the
 * plan settles the page org-wide.
 *
 * The fan-out endpoint is cached + single-flighted backend-side (ADR 0015 §Performance). Any
 * failed read yields `undefined` and the lens rows render their honest refusal — never a
 * fabricated value, never a blank page.
 */
export async function loadBreakdownLens(
  locale: string,
  searchParams?: SearchParams,
  signalId?: string,
): Promise<{ fleet: Fleet | null; lens: BreakdownLens }> {
  const params = fleetQuery(locale, searchParams);
  params.set("org_signals", "slo");
  const { fleet, org } = await fetchFleetBatchByUrl(
    `${backendUrl()}/observability/fleet-batch?${params}`,
  );
  const agents = fleet?.agents ?? [];
  if (agents.length === 0) return { fleet, lens: { kind: "monitoring" } };
  const plan = planLens(org, signalId);
  // An org-wide signal is settled by its declared capability alone: no per-agent fan-out at all.
  if (plan.kind === "masked") return { fleet, lens: { kind: "masked", signalId: plan.signalId } };
  const signals = plan.kind === "alarm" ? "slo" : "slo,scores";
  // The fan-out asks for the very window/anchor `fleetQuery` resolved for the rollup — read
  // back off `params` rather than re-derived, so the two reads cannot disagree about the clock.
  const snapshots = await fetchFleetSnapshot(signals, {
    days: params.get("period"),
    at: params.get("at"),
  });
  const perAgent: AgentSnapshot[] = agents.map((a) => ({
    agentId: a.id,
    snapshot: snapshots.get(a.id),
  }));
  return {
    fleet,
    lens:
      plan.kind === "alarm"
        ? buildAlarmLens(plan.signalId, org, perAgent)
        : buildQualityLens(perAgent),
  };
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
 * Server-side loader for the domain pages (Sécurité & Privacy, Conformité, Fiabilité & coût…):
 * the fleet rollup and one snapshot per fleet agent, in ONE backend read.
 *
 * There is no org plan step here — the domain is the page's own question, not an alarm decision —
 * so the two reads never depended on each other, and awaiting them in series bought nothing but
 * a second tunnel round-trip. They now travel together (`/observability/fleet-batch`); the rows
 * are built from the SAME builders over the SAME payloads, so the rendered table is unchanged.
 *
 * The empty fleet still renders the monitoring state. It costs the backend a snapshot fan-out it
 * used to skip (both halves are computed before the fleet is known to be empty) — a concurrent
 * read on a precomputed snapshot, against saving a round-trip on every populated page. Any failed
 * read yields honest refusal cells, never a blank page and never a fabricated value.
 */
export async function loadDomainLens(
  domain: LensDomain,
  locale: string,
  searchParams?: SearchParams,
): Promise<{ fleet: Fleet | null; lens: BreakdownLens }> {
  const params = fleetQuery(locale, searchParams);
  params.set("signals", DOMAIN_SIGNALS[domain]);
  const { fleet, snapshots } = await fetchFleetBatchByUrl(
    `${backendUrl()}/observability/fleet-batch?${params}`,
  );
  const agents = fleet?.agents ?? [];
  if (agents.length === 0) return { fleet, lens: { kind: "monitoring" } };
  const perAgent: AgentSnapshot[] = agents.map((a) => ({
    agentId: a.id,
    snapshot: snapshots.get(a.id),
  }));
  return { fleet, lens: buildDomainLens(domain, perAgent) };
}

/** The pure step: a domain's declared columns over the per-agent snapshots. */
function buildDomainLens(domain: LensDomain, perAgent: AgentSnapshot[]): BreakdownLens {
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
 * Load the fleet + the lens a page DECLARES — the single door between the page-nature registry
 * and the rendered columns. The page hands over its own route; the domain comes from
 * `PAGE_NATURE`, never from the caller, so a page declared `lens:security` structurally
 * cannot render another domain's columns. The route parameter only accepts routes whose
 * declared nature is an AgentBreakdown lens (`DeclaredLensRoute`): calling this from an
 * org-wide, monitoring or bespoke page is a compile error, not a runtime fallback.
 *
 * It returns the fleet too because it is the door that READS it: coalescing the rollup with the
 * per-agent fan-out is only possible if one place owns both, and handing the fleet back is what
 * lets the caller render the breakdown without asking for it a second time.
 *
 * The QUALITY lens keeps a second read: its org SLO read DECIDES the signal set the fan-out then
 * asks for (breach → `slo`, quiet → `slo,scores`, org-wide breach → no fan-out at all), so that
 * one genuinely depends on the other. It still coalesces what it can — the rollup rides with the
 * org read — but the fan-out stays behind, because merging it would mean asking for signals the
 * plan may turn out not to want.
 */
export async function loadDeclaredLens(
  route: DeclaredLensRoute,
  locale: string,
  opts: { fleetSearchParams?: SearchParams; signalId?: string } = {},
): Promise<{ fleet: Fleet | null; lens: BreakdownLens }> {
  const { domain } = PAGE_NATURE[route];
  return domain === "quality"
    ? loadBreakdownLens(locale, opts.fleetSearchParams, opts.signalId)
    : loadDomainLens(domain, locale, opts.fleetSearchParams);
}

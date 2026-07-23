import "server-only";

import {
  type Fleet,
  FleetSchema,
  type ReleaseControl,
  ReleaseControlSchema,
} from "@/lib/api/schemas";

import { backendHeaders, backendUrl } from "./backend";

/**
 * Server-side fleet loader, shared by the Flotte page and every GOUVERNER /
 * PLATEFORME surface that renders a per-agent breakdown + deduplicated org total.
 *
 * Returns `null` on any failure so callers render an honest empty state rather
 * than a fabricated one — never a fixture.
 */
type SearchParams = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined): string | undefined =>
  Array.isArray(value) ? value[0] : value;

/**
 * Server-side fleet loader.
 *
 * Passing `searchParams` opts the caller into the shared SURVEILLER window. A
 * caller without a temporal rail (notably the /agents directory) deliberately
 * keeps the all-history fleet contract.
 */
export async function loadFleet(locale = "fr", searchParams?: SearchParams): Promise<Fleet | null> {
  try {
    const params = new URLSearchParams({ lang: locale });
    if (searchParams) {
      params.set("period", first(searchParams.period) ?? "d7");
      const at = first(searchParams.asof) ?? first(searchParams.at) ?? first(searchParams.to);
      if (at) params.set("at", at);
    }
    const res = await fetch(`${backendUrl()}/observability/fleet?${params}`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return null;
    return FleetSchema.parse(await res.json());
  } catch {
    return null;
  }
}

/**
 * Server-side Release Control loader (AGIR), scoped by the global agent filter.
 * Returns `null` on failure so the page renders an honest empty state.
 */
export async function loadReleaseControl(
  scope: string,
  locale = "fr",
): Promise<ReleaseControl | null> {
  try {
    const res = await fetch(
      `${backendUrl()}/observability/release-control?agent=${encodeURIComponent(
        scope,
      )}&lang=${encodeURIComponent(locale)}`,
      { cache: "no-store", headers: backendHeaders({ Accept: "application/json" }) },
    );
    if (!res.ok) return null;
    return ReleaseControlSchema.parse(await res.json());
  } catch {
    return null;
  }
}

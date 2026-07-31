import "server-only";

import { cache } from "react";

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
export type SearchParams = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined): string | undefined =>
  Array.isArray(value) ? value[0] : value;

/**
 * The fleet aggregate's query params for a locale + window — the ONE place they are built.
 *
 * Two reads now ask for that window: `loadFleet` on its own route, and the coalesced
 * `/observability/fleet-batch` a domain breakdown uses. They must ask for the SAME window or a
 * page's rollup would silently disagree with itself, so the builder is shared rather than
 * copied — a convention two call sites have to remember is a convention that drifts.
 *
 * Passing `searchParams` opts into the shared SURVEILLER window (period defaulting to `d7`);
 * omitting it keeps the all-history fleet contract.
 */
export function fleetQuery(locale: string, searchParams?: SearchParams): URLSearchParams {
  const params = new URLSearchParams({ lang: locale });
  if (searchParams) {
    params.set("period", first(searchParams.period) ?? "d7");
    const at = first(searchParams.asof) ?? first(searchParams.at) ?? first(searchParams.to);
    if (at) params.set("at", at);
  }
  return params;
}

/**
 * The URL-keyed backend read behind `loadFleet`, wrapped in React `cache()`.
 *
 * The same fleet URL asked for more than once within ONE render tree — a page and
 * the breakdown it now streams, both wanting the window's fleet — hits the tunnel
 * once. The key is the fully-built URL STRING (objects compare by reference and would
 * never dedupe), so the dedup is exact: it is request-scoped and never crosses renders,
 * so freshness is byte-identical to a plain `no-store` read. Outside a render (unit
 * tests) `cache()` degrades to a passthrough — the URL and call count are unchanged.
 */
const fetchFleetByUrl = cache(async (url: string): Promise<Fleet | null> => {
  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return null;
    return FleetSchema.parse(await res.json());
  } catch {
    return null;
  }
});

/**
 * Server-side fleet loader.
 *
 * Passing `searchParams` opts the caller into the shared SURVEILLER window. A
 * caller without a temporal rail (notably the /agents directory) deliberately
 * keeps the all-history fleet contract.
 */
export async function loadFleet(locale = "fr", searchParams?: SearchParams): Promise<Fleet | null> {
  return fetchFleetByUrl(`${backendUrl()}/observability/fleet?${fleetQuery(locale, searchParams)}`);
}

/** The URL-keyed backend read behind `loadReleaseControl` (same request-scoped dedup). */
const fetchReleaseControlByUrl = cache(async (url: string): Promise<ReleaseControl | null> => {
  try {
    const res = await fetch(url, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return null;
    return ReleaseControlSchema.parse(await res.json());
  } catch {
    return null;
  }
});

/**
 * Server-side Release Control loader (AGIR), scoped by the global agent filter.
 * Returns `null` on failure so the page renders an honest empty state.
 */
export async function loadReleaseControl(
  scope: string,
  locale = "fr",
): Promise<ReleaseControl | null> {
  const url = `${backendUrl()}/observability/release-control?agent=${encodeURIComponent(
    scope,
  )}&lang=${encodeURIComponent(locale)}`;
  return fetchReleaseControlByUrl(url);
}

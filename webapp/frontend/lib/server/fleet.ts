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
export async function loadFleet(): Promise<Fleet | null> {
  try {
    const res = await fetch(`${backendUrl()}/observability/fleet`, {
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
export async function loadReleaseControl(scope: string): Promise<ReleaseControl | null> {
  try {
    const res = await fetch(
      `${backendUrl()}/observability/release-control?agent=${encodeURIComponent(scope)}`,
      { cache: "no-store", headers: backendHeaders({ Accept: "application/json" }) },
    );
    if (!res.ok) return null;
    return ReleaseControlSchema.parse(await res.json());
  } catch {
    return null;
  }
}

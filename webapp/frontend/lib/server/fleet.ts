import "server-only";

import { type Fleet, FleetSchema } from "@/lib/api/schemas";

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

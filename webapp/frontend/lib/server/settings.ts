/**
 * Server-only reader for the runtime app settings persisted by the agent.
 *
 * Currently a single flag: whether the superadmin has granted the `admin` role
 * visibility of the failure synthesis. Read directly from the backend (with the
 * service bearer) in Server Components; the write path goes through the
 * superadmin-gated route handler `app/api/settings/synthesis-access`.
 */
import "server-only";

import { cache } from "react";

import { backendHeaders, backendUrl } from "@/lib/server/backend";

/**
 * Whether `admin` may currently see the synthesis. Defaults to false on error.
 *
 * Wrapped in React `cache()` so repeated reads within one render (layout + page) share a
 * single tunnel round-trip. Request-scoped; a passthrough outside a render.
 */
export const getSynthesisAdminFlag = cache(async (): Promise<boolean> => {
  try {
    const res = await fetch(`${backendUrl()}/settings/synthesis-admin`, {
      headers: backendHeaders({ Accept: "application/json" }),
      cache: "no-store",
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { enabled?: unknown };
    return Boolean(data?.enabled);
  } catch {
    return false;
  }
});

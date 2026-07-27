import "server-only";

import { cache } from "react";

import { type ComprendreResponse, ComprendreResponseSchema } from "@/lib/api/schemas";

import { backendHeaders, backendUrl } from "./backend";

/**
 * Read and validate the public proof aggregate; contract or transport failure stays explicit.
 *
 * Wrapped in React `cache()` so the landing surface, which reads it both directly and via
 * `loadLauncherSignal`, pays one tunnel round-trip per render. Request-scoped (never across
 * renders); a passthrough outside a render, so nothing about the read changes for tests.
 */
export const loadComprendreFacts = cache(async (): Promise<ComprendreResponse> => {
  try {
    const response = await fetch(`${backendUrl()}/observability/comprendre`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!response.ok) return { available: false };
    const parsed = ComprendreResponseSchema.safeParse(await response.json());
    return parsed.success ? parsed.data : { available: false };
  } catch {
    return { available: false };
  }
});

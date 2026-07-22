import "server-only";

import { type ComprendreResponse, ComprendreResponseSchema } from "@/lib/api/schemas";

import { backendHeaders, backendUrl } from "./backend";

/** Read and validate the public proof aggregate; contract or transport failure stays explicit. */
export async function loadComprendreFacts(): Promise<ComprendreResponse> {
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
}

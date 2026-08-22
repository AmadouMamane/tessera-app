"use client";

import { useQuery } from "@tanstack/react-query";

import { fetchQualityRegimes } from "@/lib/api/client";
import type { QualityRegimeEntry } from "@/lib/api/schemas";

/**
 * The declared rating method of ONE agent, read from `/observability/quality-regimes`
 * (ADR 0017 §Amendment 4) through the same query key the quality band uses — one fetch
 * serves every consumer on the page, and the band and a chip can never disagree.
 *
 * `entry` is `undefined` while pending, on error, or for an id the registry does not
 * declare; `isError` is surfaced so a consumer can NAME the failed read instead of
 * rendering the absence as "no method" (failed-read-is-not-an-empty-result).
 */
export function useDeclaredQualityRegime(agentId: string): {
  entry: QualityRegimeEntry | undefined;
  isError: boolean;
} {
  const { data, isError } = useQuery({
    queryKey: ["quality-regimes"],
    queryFn: ({ signal }) => fetchQualityRegimes(signal),
    staleTime: 60_000,
  });
  return { entry: data?.regimes.find((e) => e.agent_id === agentId), isError };
}

"use client";

/**
 * The cockpit chrome's numbers, read once and shared.
 *
 * The sidebar and the header both need the same facts, and they render in the same tree, so
 * they ask the same React Query key: one request per locale, not one per component.
 *
 * Nothing here decides anything. Counts and tones arrive already decided by
 * `tessera.observability.chrome`, which composes the reads each destination page performs.
 * A badge whose key is absent from `badges` is a badge that does not render — an unreadable
 * source shows nothing rather than a zero, because a zero claims someone looked.
 */

import { useQuery } from "@tanstack/react-query";
import { useLocale } from "next-intl";

import { fetchChrome } from "@/lib/api/client";
import type { Chrome } from "@/lib/api/schemas";

/** The badge keys the backend may emit. Kept as a union so a typo fails `tsc`, not a render. */
export type ChromeBadgeKey = "a_traiter" | "a_faire" | "incidents" | "curation" | "signal_catalog";

export type ChromeTone = "danger" | "warning" | "neutral";

export interface ResolvedBadge {
  count: number;
  tone: ChromeTone;
}

/** 30 s, the cadence the inbox already refetches at: the badge cannot lag its own page. */
const REFETCH_MS = 30_000;

function useChrome() {
  const locale = useLocale();
  return useQuery({
    queryKey: ["chrome", locale],
    queryFn: ({ signal }) => fetchChrome(locale, signal),
    staleTime: REFETCH_MS,
    refetchInterval: REFETCH_MS,
  });
}

/**
 * The badge for one nav destination, or `null` when there is nothing honest to show.
 *
 * `null` covers three different silences on purpose — the chrome has not loaded, the
 * backend could not read the source, and the page genuinely holds nothing. None of them
 * licenses a number, and the operator learns nothing from telling them apart in a 10px dot.
 */
export function useChromeBadge(key: ChromeBadgeKey | undefined): ResolvedBadge | null {
  const { data } = useChrome();
  if (!key || !data?.available) return null;
  const badge = data.badges?.[key];
  return badge ? { count: badge.count, tone: badge.tone } : null;
}

/** Every actionable fact the bell announces, each with the page where the act is performed. */
export function useChromeNotifications(): NonNullable<Chrome["notifications"]>["items"] {
  const { data } = useChrome();
  if (!data?.available) return [];
  return data.notifications?.items ?? [];
}

"use client";

import { useSearchParams } from "next/navigation";
import { useCallback } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";

export const COCKPIT_VIEW_PARAM = "vue";

/**
 * Keep a page-level view in the URL without disturbing the page's other filters.
 *
 * The default view has no query parameter, so existing links remain canonical.
 * Focused views receive `?vue=…`, which makes them shareable and lets contextual
 * help explain the surface the operator is actually looking at.
 */
export function useUrlBackedView<K extends string>(
  values: readonly K[],
  fallback: K,
  param = COCKPIT_VIEW_PARAM,
): readonly [K, (next: K) => void] {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const raw = searchParams.get(param);
  const active = values.includes(raw as K) ? (raw as K) : fallback;

  const setActive = useCallback(
    (next: K) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next === fallback) params.delete(param);
      else params.set(param, next);
      const query = params.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [fallback, param, pathname, router, searchParams],
  );

  return [active, setActive] as const;
}

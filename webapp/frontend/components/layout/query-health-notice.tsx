"use client";

import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";

/** Count failed queries that still have a visible consumer on the current page. */
export function activeErrorQueryCount(queryClient: QueryClient): number {
  return queryClient
    .getQueryCache()
    .getAll()
    .filter((query) => query.getObserversCount() > 0 && query.state.status === "error").length;
}

/**
 * Page-level data health for the cockpit.
 *
 * Many dashboard cards can preserve previous data while revalidating. When a
 * live read fails, this notice prevents stale values or empty fallbacks from
 * being mistaken for a current measurement and offers one restrained retry.
 */
export function QueryHealthNotice() {
  const t = useTranslations("queryHealth");
  const queryClient = useQueryClient();
  const [retrying, setRetrying] = useState(false);
  const subscribe = useCallback(
    (onStoreChange: () => void) =>
      queryClient.getQueryCache().subscribe(() => {
        onStoreChange();
      }),
    [queryClient],
  );
  const getSnapshot = useCallback(() => activeErrorQueryCount(queryClient), [queryClient]);
  const count = useSyncExternalStore(subscribe, getSnapshot, () => 0);

  if (count === 0) return null;

  async function retry() {
    setRetrying(true);
    try {
      await queryClient.refetchQueries({
        type: "active",
        predicate: (query) => query.state.status === "error",
      });
    } finally {
      setRetrying(false);
    }
  }

  return (
    <aside
      role="alert"
      data-slot="query-health-notice"
      className="flex min-h-11 flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-amber-500/30 bg-amber-500/[0.08] px-3 py-2 shadow-[inset_3px_0_0_color-mix(in_oklch,var(--tessera-fg-warning)_78%,transparent)] backdrop-blur-sm"
    >
      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-amber-500/12 text-[var(--tessera-fg-warning)]">
        <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-[var(--tessera-text)]">{t("title")}</p>
        <p className="text-[0.68rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {t(count === 1 ? "detailOne" : "detailMany", { count })}
        </p>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={retry}
        disabled={retrying}
        className="ml-auto border-amber-500/25 bg-[var(--tessera-surface)]/70"
      >
        <RefreshCw className={retrying ? "animate-spin motion-reduce:animate-none" : undefined} />
        {retrying ? t("retrying") : t("retry")}
      </Button>
    </aside>
  );
}

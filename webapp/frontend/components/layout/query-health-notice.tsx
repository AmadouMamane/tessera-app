"use client";

import { type QueryClient, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, RefreshCw, TriangleAlert } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useState, useSyncExternalStore } from "react";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { ApiError } from "@/lib/api/client";

export type QueryFailureKind = "contract" | "access" | "service" | "network" | "response";

export interface ActiveQueryFailure {
  hash: string;
  source: string;
  label: string | undefined;
  href: string | undefined;
  kind: QueryFailureKind;
  dataUpdatedAt: number;
}

/** Classify the failure without leaking raw transport or validation text into the cockpit. */
export function queryFailureKind(error: unknown): QueryFailureKind {
  if (error instanceof ApiError) {
    if (error.status === 200) return "contract";
    if (error.status === 401 || error.status === 403) return "access";
    if (error.status >= 500) return "service";
    return "response";
  }
  return "network";
}

function sourceFromKey(key: readonly unknown[]): string {
  const first = String(key[0] ?? "data");
  const words = first.replaceAll(/[-_]+/g, " ").trim();
  return words.length > 0 ? `${words[0]?.toUpperCase() ?? ""}${words.slice(1)}` : "Data";
}

/** Failed queries with at least one ENABLED observer on the current screen. */
export function activeErrorQueries(queryClient: QueryClient): ActiveQueryFailure[] {
  return queryClient
    .getQueryCache()
    .getAll()
    .filter((query) => query.isActive() && query.state.status === "error")
    .map((query) => ({
      hash: query.queryHash,
      source: sourceFromKey(query.queryKey),
      label: query.meta?.health?.label,
      href: query.meta?.health?.href,
      kind: queryFailureKind(query.state.error),
      dataUpdatedAt: query.state.dataUpdatedAt,
    }));
}

/** Count failed queries that still have a visible consumer on the current page. */
export function activeErrorQueryCount(queryClient: QueryClient): number {
  return activeErrorQueries(queryClient).length;
}

function activeErrorSignature(queryClient: QueryClient): string {
  return activeErrorQueries(queryClient)
    .map((failure) => `${failure.hash}:${failure.kind}:${failure.dataUpdatedAt}`)
    .join("|");
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
  const locale = useLocale();
  const queryClient = useQueryClient();
  const [retrying, setRetrying] = useState(false);
  const subscribe = useCallback(
    (onStoreChange: () => void) =>
      queryClient.getQueryCache().subscribe(() => {
        onStoreChange();
      }),
    [queryClient],
  );
  const getSnapshot = useCallback(() => activeErrorSignature(queryClient), [queryClient]);
  useSyncExternalStore(subscribe, getSnapshot, () => "");
  const failures = activeErrorQueries(queryClient);
  const count = failures.length;

  if (count === 0) return null;

  async function retry() {
    setRetrying(true);
    try {
      await queryClient.refetchQueries({
        type: "active",
        predicate: (query) => query.isActive() && query.state.status === "error",
      });
    } finally {
      setRetrying(false);
    }
  }

  return (
    <aside
      role="alert"
      data-slot="query-health-notice"
      className="flex min-h-11 flex-col gap-2 rounded-lg border border-amber-500/30 bg-amber-500/[0.08] px-3 py-2.5 shadow-[inset_3px_0_0_color-mix(in_oklch,var(--tessera-fg-warning)_78%,transparent)] backdrop-blur-sm"
    >
      <div className="flex w-full flex-wrap items-center gap-2.5">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-md bg-amber-500/12 text-[var(--tessera-fg-warning)]">
          <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <p className="min-w-0 flex-1 text-xs font-semibold text-[var(--tessera-text)]">
          {t(count === 1 ? "titleOne" : "titleMany", { count })}
        </p>
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
      </div>
      <ul className="grid w-full gap-1.5 sm:grid-cols-2">
        {failures.slice(0, 4).map((failure) => {
          const label = failure.label ?? t("sourceFallback", { source: failure.source });
          const lastSuccess = failure.dataUpdatedAt
            ? t("lastSuccess", {
                time: new Intl.DateTimeFormat(locale, {
                  hour: "2-digit",
                  minute: "2-digit",
                }).format(failure.dataUpdatedAt),
              })
            : t("noSuccess");
          return (
            <li
              key={failure.hash}
              className="min-w-0 rounded-md border border-amber-500/15 bg-[var(--tessera-surface)]/45 px-2.5 py-2"
            >
              <div className="flex min-w-0 items-center gap-1.5">
                {failure.href ? (
                  <Link
                    href={failure.href}
                    className="truncate text-[0.7rem] font-semibold text-[var(--tessera-text)] underline-offset-2 hover:underline"
                  >
                    {label}
                  </Link>
                ) : (
                  <span className="truncate text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                    {label}
                  </span>
                )}
                {failure.href ? (
                  <ArrowUpRight className="h-3 w-3 shrink-0" aria-hidden="true" />
                ) : null}
              </div>
              <p className="mt-0.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {t(`kind.${failure.kind}`)} · {lastSuccess}
              </p>
            </li>
          );
        })}
      </ul>
      {count > 4 ? (
        <p className="text-[0.64rem] text-[var(--tessera-text-muted)]">
          {t("more", { count: count - 4 })}
        </p>
      ) : null}
    </aside>
  );
}

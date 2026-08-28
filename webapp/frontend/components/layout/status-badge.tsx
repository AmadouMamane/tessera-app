"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { fetchHealth } from "@/lib/api/client";

export function StatusBadge() {
  const t = useTranslations("health.status");

  const { data, isError } = useQuery({
    queryKey: ["health-badge"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 15_000,
    retry: 1,
    staleTime: 10_000,
  });

  if (isError || data?.status === "down") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-red-500/20 bg-red-500/10 px-2.5 py-1 text-xs font-medium text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-400">
        <span className="h-1.5 w-1.5 rounded-full bg-red-500 dark:bg-red-400" />
        {t("down")}
      </span>
    );
  }

  if (data?.status === "degraded") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 text-xs font-medium text-amber-600 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-400">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500 dark:bg-amber-400" />
        {t("degraded")}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/20 bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-600 dark:border-green-400/20 dark:bg-green-400/10 dark:text-green-400">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-500 dark:bg-green-400" />
      {t("ok")}
    </span>
  );
}

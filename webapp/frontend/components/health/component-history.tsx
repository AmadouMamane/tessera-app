"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, History, Search } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { humanSeconds, verdictTone } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponentHistory } from "@/lib/api/client";
import type { ComponentAvailability } from "@/lib/api/schemas";

const POLL_MS = 60_000;
const WINDOWS = [1, 7, 30] as const;
type Window = (typeof WINDOWS)[number];

/**
 * The time dimension: how each component fared, and — the part a poll-and-render page throws
 * away entirely — every time one of them CHANGED.
 *
 * A component that fell and came back between two fifteen-second polls used to leave no trace
 * anywhere in this system. It now leaves a transition, and the transition says whether it was
 * *witnessed* (both sides seen within the continuity window) or merely *discovered* after a
 * hole in the record.
 *
 * Every percentage here is a share of OBSERVED time, and the observed share is rendered next to
 * it rather than in a footnote. The probe runs when the cockpit asks, so a window is watched in
 * patches: "99.9 % available" over a day watched for four hours is a true statement about four
 * hours. A reader given the first number without the second has been misled by omission — which
 * is why the two are one cell here and not two columns that can be read apart.
 */
export function ComponentHistoryPanel() {
  const t = useTranslations("health.history");
  const format = useFormatter();
  const [days, setDays] = useState<Window>(1);

  const query = useQuery({
    queryKey: ["component-history", days],
    queryFn: ({ signal }) => fetchComponentHistory(days, signal),
    refetchInterval: POLL_MS,
  });

  const rows = query.data?.availability ?? [];
  const changes = query.data?.transitions ?? [];
  // Nothing recorded is its own state. It is NOT "everything was fine": the journal is written
  // by the probe, so an empty one means nobody has looked yet, and rendering that as a healthy
  // window is precisely the manufactured uptime this block exists to refuse.
  const nothingRecorded = query.data !== undefined && rows.length === 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <History className="h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        <div className="flex items-center gap-1">
          {WINDOWS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`rounded-md px-1.5 py-0.5 text-[0.66rem] transition-colors ${
                option === days
                  ? "bg-[var(--tessera-muted)] font-medium text-[var(--foreground)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {t(`window.${option}`)}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-28 w-full" />
        ) : query.error || !query.data ? (
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : nothingRecorded ? (
          <p className="text-xs text-[var(--muted-foreground)]">{t("nothingRecorded")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <AvailabilityTable rows={rows} />
            <div>
              <p className="mb-1 text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                {t("transitions", { n: changes.length })}
              </p>
              {changes.length === 0 ? (
                <p className="text-xs text-[var(--muted-foreground)]">{t("noTransitions")}</p>
              ) : (
                <ul className="flex flex-col gap-0.5">
                  {changes.slice(0, 8).map((change) => (
                    <li
                      key={`${change.component}-${change.at}`}
                      className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.7rem]"
                    >
                      <span className="font-medium text-[var(--foreground)]">
                        {change.component}
                      </span>
                      <Badge tone={verdictTone(change.from)}>{t(`state.${change.from}`)}</Badge>
                      <ArrowRight className="h-3 w-3 shrink-0 text-[var(--muted-foreground)]" />
                      <Badge tone={verdictTone(change.to)}>{t(`state.${change.to}`)}</Badge>
                      <span className="text-[0.66rem] text-[var(--muted-foreground)]">
                        {format.relativeTime(new Date(change.at))}
                      </span>
                      {/* Witnessed or merely found? The instant means different things, and a
                          reader acting on a timestamp deserves to know which one it is. */}
                      {change.after_gap ? (
                        <span
                          className="flex items-center gap-0.5 text-[0.62rem] text-[var(--tessera-fg-warning)]"
                          title={t("discoveredTitle")}
                        >
                          <Search className="h-2.5 w-2.5" />
                          {t("discovered")}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AvailabilityTable({ rows }: { rows: ComponentAvailability[] }) {
  const t = useTranslations("health.history");
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-fixed border-collapse text-left text-[0.72rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
            <th className="w-[9rem] px-1.5 py-1 font-medium 2xl:w-[11rem]">{t("col.component")}</th>
            <th className="px-1.5 py-1 text-center font-medium">{t("col.ok")}</th>
            <th className="px-1.5 py-1 text-center font-medium">{t("col.observed")}</th>
            <th className="w-[30%] px-1.5 py-1 pr-2 text-right font-medium">{t("col.detail")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const unobserved = row.observed_seconds <= 0;
            return (
              <tr
                key={row.component}
                className="border-b border-[var(--tessera-border)]/60 last:border-0"
              >
                <td className="truncate px-1.5 py-1 font-medium text-[var(--foreground)]">
                  {row.component}
                </td>
                <td className="px-1.5 py-1 text-center tabular-nums">
                  {/* Never a number the record cannot support — and there are TWO such cases.
                      Nobody watched, and watched the whole time through a blind spot: in both,
                      any percentage is a claim about the component made out of a fact about the
                      probe, so the cell says "cannot say" and the reason travels in the title. */}
                  {row.ok_ratio === null ? (
                    <span
                      className="text-[var(--muted-foreground)]"
                      title={
                        row.observed_seconds > 0 ? t("blindThroughout") : t("neverObservedTitle")
                      }
                    >
                      {t("cannotSay")}
                    </span>
                  ) : (
                    <span
                      className={
                        row.ok_ratio >= 0.999
                          ? "text-[var(--tessera-fg-success)]"
                          : "text-[var(--tessera-fg-warning)]"
                      }
                    >
                      {(row.ok_ratio * 100).toFixed(1)} %
                    </span>
                  )}
                </td>
                <td
                  className="px-1.5 py-1 text-center tabular-nums text-[var(--muted-foreground)]"
                  title={t("observedTitle", {
                    observed: humanSeconds(row.observed_seconds),
                    window: humanSeconds(row.window_seconds),
                    decidable: humanSeconds(row.decidable_seconds),
                  })}
                >
                  {(row.observed_ratio * 100).toFixed(row.observed_ratio < 0.1 ? 1 : 0)} %
                </td>
                <td className="px-1.5 py-1 pr-2 text-right text-[0.66rem] text-[var(--muted-foreground)]">
                  {unobserved
                    ? t("unobserved")
                    : Object.entries(row.seconds_by_verdict)
                        .filter(([, seconds]) => seconds > 0)
                        .map(
                          ([verdict, seconds]) =>
                            `${t(`state.${verdict}`)} ${humanSeconds(seconds)}`,
                        )
                        .join(" · ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

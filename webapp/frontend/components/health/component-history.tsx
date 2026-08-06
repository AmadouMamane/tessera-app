"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, History, Search } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { ComponentTimeline } from "@/components/health/component-timeline";
import { humanSeconds, relativeNow, verdictTone } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponentHistory } from "@/lib/api/client";
import type { ComponentAvailability, ComponentHistory } from "@/lib/api/schemas";

const POLL_MS = 60_000;
const WINDOWS = [1, 7, 30] as const;
type Window = (typeof WINDOWS)[number];
const TRANSITIONS_FOLDED = 8;

/**
 * The time dimension: how each component fared, WHEN it changed — and, since ADR 0052
 * §Amendment 1, whether anybody is steadily looking.
 *
 * The timeline is the block's reason to exist: a phase is ink, a hole in the record is the
 * empty track, and neither is ever bridged. Every percentage still travels with the share of
 * the window that was observed, and the scheduler's own heartbeat is reported from the stamp
 * the leader loop writes — never from configuration, so a dead loop reads as « arrêtée » and
 * not as reassurance.
 */
export function ComponentHistoryPanel() {
  const t = useTranslations("health.history");
  const format = useFormatter();
  const [days, setDays] = useState<Window>(1);
  const [allTransitions, setAllTransitions] = useState(false);

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
  const shown = allTransitions ? changes : changes.slice(0, TRANSITIONS_FOLDED);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm">
          <History className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-info)]" />
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        <div className="flex items-center gap-0.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-muted)]/30 p-0.5">
          {WINDOWS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`rounded-md px-2 py-0.5 text-[0.66rem] transition-colors ${
                option === days
                  ? "bg-[var(--tessera-surface)] font-medium text-[var(--foreground)] shadow-sm"
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
          <Skeleton className="h-32 w-full" />
        ) : query.error || !query.data ? (
          <QueryErrorState
            compact
            onRetry={() => void query.refetch()}
            retrying={query.isRefetching}
          />
        ) : (
          <div className="flex flex-col gap-3">
            <SchedulerLine data={query.data} />
            {nothingRecorded ? (
              <p className="text-xs text-[var(--muted-foreground)]">{t("nothingRecorded")}</p>
            ) : (
              <>
                <TimelineTable data={query.data} rows={rows} days={days} />
                {/* Why a hole is a hole: the reader who just saw an empty stretch of track is
                    told the rule that refused to paint over it. */}
                <p className="text-[0.62rem] leading-relaxed text-[var(--muted-foreground)]">
                  {t("holesFootnote", {
                    continuity: humanSeconds(query.data.continuity_window_s),
                    from: format.dateTime(new Date(query.data.window.since), {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                    to: format.dateTime(new Date(query.data.window.until), {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    }),
                  })}
                </p>
                <div>
                  <p className="mb-1 text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
                    {t("transitions", { n: changes.length })}
                  </p>
                  {changes.length === 0 ? (
                    <p className="text-xs text-[var(--muted-foreground)]">{t("noTransitions")}</p>
                  ) : (
                    <>
                      <ul className="flex flex-col gap-0.5">
                        {shown.map((change) => (
                          <li
                            key={`${change.component}-${change.at}`}
                            className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.7rem]"
                          >
                            <span className="font-medium text-[var(--foreground)]">
                              {change.component}
                            </span>
                            <Badge tone={verdictTone(change.from)}>
                              {t(`state.${change.from}`)}
                            </Badge>
                            <ArrowRight className="h-3 w-3 shrink-0 text-[var(--muted-foreground)]" />
                            <Badge tone={verdictTone(change.to)}>{t(`state.${change.to}`)}</Badge>
                            <span className="text-[0.66rem] text-[var(--muted-foreground)]">
                              {format.relativeTime(new Date(change.at), relativeNow())}
                            </span>
                            {/* Witnessed or merely found? The instant means different things,
                                and a reader acting on a timestamp deserves to know which. */}
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
                      {changes.length > TRANSITIONS_FOLDED ? (
                        <button
                          type="button"
                          onClick={() => setAllTransitions((value) => !value)}
                          className="mt-1 text-[0.66rem] text-[var(--tessera-green)] transition-colors hover:underline"
                        >
                          {allTransitions
                            ? t("showLess")
                            : t("showAll", { n: changes.length - TRANSITIONS_FOLDED })}
                        </button>
                      ) : null}
                    </>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * The scheduler's heartbeat, as one visible line. Three states, three repairs — and the line
 * is derived from the stamp the loop wrote, so a dead leader cannot read as a running watch.
 */
function SchedulerLine({ data }: { data: ComponentHistory }) {
  const t = useTranslations("health.history");
  const format = useFormatter();
  const probe = data.probe;
  const dot =
    probe.state === "active"
      ? "bg-[var(--tessera-green)]"
      : probe.state === "stale"
        ? "bg-[var(--tessera-fg-warning)]"
        : "bg-[var(--muted-foreground)]";
  const lastSeen =
    probe.last_run_at === null
      ? null
      : format.relativeTime(new Date(probe.last_run_at), relativeNow());
  const sentence =
    probe.state === "active" && probe.interval_s !== null && lastSeen !== null
      ? t("probeActive", { every: humanSeconds(probe.interval_s), last: lastSeen })
      : probe.state === "stale" && lastSeen !== null
        ? t("probeStale", { last: lastSeen })
        : probe.interval_s !== null
          ? t("probeNever", { every: humanSeconds(probe.interval_s) })
          : t("probeOnDemand");
  return (
    <p className="flex items-center gap-1.5 text-[0.66rem] text-[var(--muted-foreground)]">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      {sentence}
    </p>
  );
}

function TimelineTable({
  data,
  rows,
  days,
}: {
  data: ComponentHistory;
  rows: ComponentAvailability[];
  days: number;
}) {
  const t = useTranslations("health.history");
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[42rem] table-fixed border-collapse text-left text-[0.72rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
            <th className="w-[9rem] px-1.5 py-1 font-medium 2xl:w-[11rem]">{t("col.component")}</th>
            <th className="px-1.5 py-1 font-medium">{t("col.timeline")}</th>
            <th className="w-[5.5rem] px-1.5 py-1 text-center font-medium">{t("col.ok")}</th>
            <th className="w-[5rem] px-1.5 py-1 text-center font-medium">{t("col.observed")}</th>
            <th className="w-[20%] px-1.5 py-1 pr-2 text-right font-medium">{t("col.detail")}</th>
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
                <td className="truncate px-1.5 py-1.5 font-medium text-[var(--foreground)]">
                  {row.component}
                </td>
                <td className="px-1.5 py-1.5">
                  <ComponentTimeline
                    phases={data.phases}
                    component={row.component}
                    since={data.window.since}
                    until={data.window.until}
                    days={days}
                  />
                </td>
                <td className="px-1.5 py-1.5 text-center tabular-nums">
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
                  className="px-1.5 py-1.5 text-center tabular-nums text-[var(--muted-foreground)]"
                  title={t("observedTitle", {
                    observed: humanSeconds(row.observed_seconds),
                    window: humanSeconds(row.window_seconds),
                    decidable: humanSeconds(row.decidable_seconds),
                  })}
                >
                  {(row.observed_ratio * 100).toFixed(row.observed_ratio < 0.1 ? 1 : 0)} %
                </td>
                <td className="px-1.5 py-1.5 pr-2 text-right text-[0.66rem] text-[var(--muted-foreground)]">
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

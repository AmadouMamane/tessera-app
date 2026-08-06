"use client";

import { useQuery } from "@tanstack/react-query";
import { Ban, CircleSlash, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { stateTone } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";

const POLL_MS = 15_000;

/**
 * What each store carries as a verdict — the chain between this page and the rest of the cockpit.
 *
 * Until now nothing on this page connected a red component to a consequence. That is the gap
 * that made it a *health* page: an operator could see ClickHouse was down and had no way to
 * learn that turn evidence had just become "cannot say", and that an agent might therefore be
 * refused at the release gate. The store and the blocked agent lived on two screens with no
 * sentence between them.
 *
 * Two things are kept visibly apart, because they are not the same kind of claim:
 *
 * * the capability is **declared** — which module reads which store is a fact about this
 *   codebase, and `reads` cites it so the claim is checkable;
 * * the state is **measured** — computed from the probe, never asserted, and `cannot_say` when
 *   a dependency could not be interrogated.
 *
 * The rows that can BLOCK an agent are marked. An operator triages on that and nothing else:
 * a blank chart waits until morning, a refused agent does not.
 */
export function StoreConsequences() {
  const t = useTranslations("health.consequences");

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  const rows = query.data?.consequences ?? [];
  const atRisk = rows.filter((row) => row.state !== "served");

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data ? (
          <Badge tone={atRisk.length === 0 ? "success" : "warning"}>
            {atRisk.length === 0
              ? t("allServed", { n: rows.length })
              : t("atRisk", { n: atRisk.length, total: rows.length })}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : query.error || !query.data ? (
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : (
          <ul className="flex flex-col gap-1">
            {rows.map((row) => {
              const tone = stateTone(row.state);
              const Icon = row.state === "served" ? null : row.state === "lost" ? Ban : CircleSlash;
              return (
                <li
                  key={row.key}
                  className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 border-b border-[var(--tessera-border)]/50 py-1 last:border-0"
                >
                  <span className="flex items-center gap-1 text-[0.72rem] font-medium text-[var(--foreground)]">
                    {row.gates_agents ? (
                      <ShieldAlert
                        className="h-3 w-3 shrink-0 text-[var(--tessera-fg-warning)]"
                        aria-label={t("gatesAgents")}
                      />
                    ) : null}
                    {t(`capability.${row.key}`)}
                  </span>
                  <Badge tone={tone}>
                    {Icon ? <Icon className="h-3 w-3" /> : null}
                    {t(`state.${row.state}`)}
                  </Badge>
                  {/* The row names the component to restart. Leaving the operator to intersect
                      "which capability" with "which component is red" by eye is the work this
                      block exists to remove. */}
                  {row.because.length > 0 ? (
                    <span className="text-[0.66rem] text-[var(--muted-foreground)]">
                      {t("because", { list: row.because.join(", ") })}
                    </span>
                  ) : null}
                  {row.gates_agents && row.state !== "served" ? (
                    <span className="text-[0.66rem] text-[var(--tessera-fg-warning)]">
                      {t("mayBlockAgents")}
                    </span>
                  ) : null}
                  <span
                    className="ml-auto truncate font-mono text-[0.6rem] text-[var(--muted-foreground)]"
                    title={t("readsTitle", { module: row.reads })}
                  >
                    {row.reads}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

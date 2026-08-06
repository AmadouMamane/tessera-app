"use client";

import { useQuery } from "@tanstack/react-query";
import { useFormatter, useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { observedAt } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";

const POLL_MS = 15_000;

/**
 * The stack's components, as the preflight witness sees them.
 *
 * This page used to render four KPI cards fed by `/healthz` and `/readyz` — two probes about
 * the agent process — while its own contextual help promised a component list with a last
 * check and its dependencies. On 2026-08-05 `tessera.preflight` reported ClickHouse FAIL and
 * this page showed everything operational, because nothing on it could go red for a dependency.
 *
 * Three verdicts, not two. `blind` — the probe could not look at all — is rendered as its own
 * state and never as "ok": a witness that cannot see may not report ok (ADR 0026). A reader who
 * cannot tell "the database is down" from "nobody asked the database" has no information.
 */
export function ComponentsPanel() {
  const t = useTranslations("health.components");
  const format = useFormatter();

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  const tone = (verdict: string) =>
    verdict === "ok" ? "success" : verdict === "fail" ? "danger" : "warning";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data ? (
          <div className="flex items-center gap-2">
            {/* The observation instant, published because it is NOT the render instant: the
                probe is cached, and a component list that does not say when it last looked
                invites the reader to assume "now". */}
            <span className="text-[0.66rem] text-[var(--muted-foreground)]">
              {t("checked", {
                when: format.relativeTime(observedAt(query.data.observed_at)),
              })}
            </span>
            <Badge tone={tone(query.data.verdict === "clear" ? "ok" : query.data.verdict)}>
              {t(`verdict.${query.data.verdict}`, {
                ok: query.data.counts.stack_ok,
                total: query.data.counts.stack_total,
              })}
            </Badge>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : query.error ? (
          // A failed READ is not an empty result: say the read failed, never "0 components".
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : query.data && query.data.components.length > 0 ? (
          // `table-fixed`, per docs/table-rhythm-playbook.md: auto layout hands its leftover
          // width to a column of its own choosing and the choice changes with the viewport,
          // which is what "the columns look random" is. The identity column is sized to its
          // content and left-aligned; the prose column takes a flat share, right-aligned, so
          // its leading air matches its neighbours' instead of being whatever is left.
          <div className="overflow-x-auto">
            <table className="w-full table-fixed border-collapse text-left text-[0.72rem]">
              <thead>
                <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
                  <th className="w-[8.5rem] px-1.5 py-1 font-medium 2xl:w-[10rem]">
                    {t("col.name")}
                  </th>
                  <th className="w-[6rem] px-1.5 py-1 font-medium">{t("col.verdict")}</th>
                  <th className="px-1.5 py-1 font-medium">{t("col.interrogates")}</th>
                  <th className="w-[38%] px-1.5 py-1 pr-2 text-right font-medium">
                    {t("col.detail")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(["stack", "precondition"] as const).flatMap((group) => {
                  const rows = query.data.components.filter((c) => c.group === group);
                  if (rows.length === 0) return [];
                  return [
                    <tr key={`h-${group}`}>
                      <th
                        colSpan={4}
                        className="px-1.5 pb-1 pt-3 text-left text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]"
                      >
                        <span className="flex items-baseline gap-2">
                          {t(`group.${group}`, { n: rows.length })}
                          {/* The two halves answer DIFFERENT questions and were rendered
                              identically: Grafana being down is not the agent being broken.
                              A reader who cannot tell the groups apart looks in the wrong
                              place, which is the failure this whole page is about. */}
                          <span className="font-normal normal-case tracking-normal text-[var(--muted-foreground)]/70">
                            {t(`groupAsks.${group}`)}
                          </span>
                        </span>
                      </th>
                    </tr>,
                    ...rows.map((component) => (
                      <tr
                        key={`${group}-${component.name}`}
                        className="border-b border-[var(--tessera-border)]/60 last:border-0"
                      >
                        <td className="truncate px-1.5 py-1 font-medium text-[var(--foreground)]">
                          {component.name}
                        </td>
                        <td className="px-1.5 py-1">
                          <Badge tone={tone(component.verdict)}>
                            {t(`state.${component.verdict}`)}
                          </Badge>
                        </td>
                        <td className="truncate px-1.5 py-1 text-[var(--muted-foreground)]">
                          {component.interrogates || "—"}
                        </td>
                        <td
                          className="truncate px-1.5 py-1 pr-2 text-right font-mono text-[0.66rem] text-[var(--muted-foreground)]"
                          title={component.detail}
                        >
                          {component.detail}
                        </td>
                      </tr>
                    )),
                  ];
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-[var(--muted-foreground)]">{t("empty")}</p>
        )}
      </CardContent>
    </Card>
  );
}

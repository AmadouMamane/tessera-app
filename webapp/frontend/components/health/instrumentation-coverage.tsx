"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge } from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchInstrumentationCoverage } from "@/lib/api/client";

const POLL_MS = 60_000;

/**
 * Signal 92 — how much of the L1 span contract each agent actually stamps.
 *
 * The agent-observability number this page never carried. It was not missing from the codebase:
 * `coverage_descriptor` has computed it since step 6b, reachable only as
 * `/observability/quality-nets?agent=<id>` — one agent at a time, from a page that never called
 * it. A fleet has no per-agent page to ask from, so a computable number went uncomputed.
 *
 * The label says what it measures and no more. The evidence is the Scope dimensions carried on
 * business events, not a span store: spans and events carry the same dimensions by design, so
 * event-field presence is the honestly available proxy — and the card names it, because
 * "instrumentation coverage" with no source reads as a claim about spans.
 *
 * Three statuses, and the last two are not the same fact. `no_evidence` is a store that answered
 * "none"; `unverifiable` is a store that did not answer. Rendering the second as 0 % turns a
 * ClickHouse outage into a fleet that instruments nothing.
 */
export function InstrumentationCoverage() {
  const t = useTranslations("health.coverage");

  const query = useQuery({
    queryKey: ["instrumentation-coverage"],
    queryFn: ({ signal }) => fetchInstrumentationCoverage(signal),
    refetchInterval: POLL_MS,
  });

  const agents = query.data?.agents ?? [];
  const measured = agents.filter((agent) => agent.covered_pct !== null);
  // Agents this evidence cannot speak about at all. Counted apart from the fleet figure and
  // named on the card, so "100 % sur 1 agent mesuré" cannot be read as "1 of 6 is instrumented".
  const inapplicable = agents.filter((agent) => agent.status === "not_applicable").length;
  const fleetPct =
    measured.length > 0
      ? measured.reduce((total, agent) => total + (agent.covered_pct ?? 0), 0) / measured.length
      : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 font-sans text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
          <Gauge className="h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data ? (
          query.data.blind ? (
            <Badge tone="warning">{t("blind")}</Badge>
          ) : (
            <Badge tone={fleetPct !== null && fleetPct >= 99 ? "success" : "warning"}>
              {fleetPct === null
                ? t("noneMeasured")
                : t("fleet", { pct: fleetPct.toFixed(0), n: measured.length })}
            </Badge>
          )
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-20 w-full" />
        ) : query.error || !query.data ? (
          <Badge tone="danger">{t("unreadable")}</Badge>
        ) : agents.length === 0 ? (
          <p className="text-xs text-[var(--muted-foreground)]">{t("noAgents")}</p>
        ) : (
          <>
            <ul className="flex flex-col gap-1">
              {agents.map((agent) => (
                <li
                  key={agent.agent_id}
                  className="flex flex-wrap items-center gap-x-2 gap-y-0.5 border-b border-[var(--tessera-border)]/50 py-1 text-[0.72rem] last:border-0"
                >
                  <span className="w-[8rem] shrink-0 truncate font-medium text-[var(--foreground)]">
                    {agent.agent_id}
                  </span>
                  {agent.covered_pct === null ? (
                    // `not_applicable` is neutral, never amber: an agent with no business
                    // grammar is behaving correctly, and an amber chip beside "aucune
                    // télémétrie" told five healthy agents' operators they were broken.
                    <Badge tone={agent.status === "not_applicable" ? "neutral" : "warning"}>
                      {t(`status.${agent.status}`)}
                    </Badge>
                  ) : (
                    <>
                      {/* The bar is the measurement, so it only exists where there IS one. An
                          empty bar beside "unverifiable" would read as zero. */}
                      <span className="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-[var(--tessera-muted)]">
                        <span
                          className={`block h-full rounded-full ${
                            agent.covered_pct >= 100
                              ? "bg-[var(--tessera-green)]"
                              : "bg-[var(--tessera-fg-warning)]"
                          }`}
                          style={{ width: `${Math.min(100, agent.covered_pct)}%` }}
                        />
                      </span>
                      <span className="tabular-nums text-[var(--foreground)]">
                        {agent.covered_pct.toFixed(0)} %
                      </span>
                    </>
                  )}
                  {agent.missing_attributes.length > 0 ? (
                    <span
                      className="truncate text-[0.64rem] text-[var(--tessera-fg-warning)]"
                      title={agent.missing_attributes.join(", ")}
                    >
                      {t("missing", { list: agent.missing_attributes.join(", ") })}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
            {/* Named on the card, not only in the tooltip: "instrumentation coverage" with no
                source reads as a claim about spans, and this measures event fields. */}
            <p className="mt-1.5 text-[0.62rem] text-[var(--muted-foreground)]">
              {t("proxy", { n: query.data.required_attributes.length })}
              {inapplicable > 0 ? ` ${t("inapplicable", { n: inapplicable })}` : ""}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}

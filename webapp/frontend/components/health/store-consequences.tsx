"use client";

import { useQuery } from "@tanstack/react-query";
import { Ban, CircleSlash, SearchCheck, ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { stateTone } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";
import type { ConsequenceState } from "@/lib/api/schemas";

const POLL_MS = 15_000;

/** Broken first, undecidable next, held last — an operator triages downward. */
const STATE_ORDER: Record<ConsequenceState, number> = { lost: 0, cannot_say: 1, served: 2 };

/**
 * What each store carries as a verdict — the chain between this page and the rest of the cockpit.
 *
 * Until now nothing on this page connected a red component to a consequence. That is the gap
 * that made it a *health* page: an operator could see ClickHouse was down and had no way to
 * learn that turn evidence had just become "cannot say", and that an agent might therefore be
 * refused at the release gate. The store and the blocked agent lived on two screens with no
 * sentence between them.
 *
 * The module that reads each store is EVIDENCE — it makes the declared capability checkable —
 * but it is a pointer into the codebase, so it lives in the row's tooltip rather than on the
 * card. The line: an address, an HTTP status or an errno is a fact about the RUNNING SYSTEM and
 * stays visible, because it is what somebody diagnosing an outage reads next; a source path is a
 * fact about the repository, and an operator cannot act on it.
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
  // What is broken reads first. The declaration order is the codebase's, not the operator's,
  // and it buried the only row that needed an answer in sixth position out of seven.
  const ordered = [...rows].sort((a, b) => STATE_ORDER[a.state] - STATE_ORDER[b.state]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm">
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
          <QueryErrorState
            compact
            onRetry={() => void query.refetch()}
            retrying={query.isRefetching}
          />
        ) : (
          <ul className="flex flex-col gap-1">
            {ordered.map((row) => {
              const tone = stateTone(row.state);
              const Icon = row.state === "served" ? null : row.state === "lost" ? Ban : CircleSlash;
              return (
                <li
                  key={row.key}
                  // The module that performs the read is EVIDENCE — it is what makes the declared
                  // capability checkable — but it is a pointer into the codebase, and a source
                  // path is not something an operator can act on. It moves here, one hover away,
                  // and off the face of the card. The line this draws: an ADDRESS, an HTTP status
                  // or an errno is a fact about the RUNNING SYSTEM and stays visible, because it
                  // is what somebody diagnosing an outage reads next; a file path is a fact about
                  // the repository and belongs where a developer looks for it.
                  title={`${t(`capability.${row.key}`)} — ${t("readsTitle", { module: row.reads })}`}
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
                  {/* Which dependencies carried an ADAPTER-LEVEL read this cycle (ADR 0052
                      Am.1.3): « assurée » over a socket-only check must not be mistaken for
                      the stronger claim, so the stronger claim is marked and named. */}
                  {row.checked_by_read.length > 0 ? (
                    <span
                      className="flex items-center gap-0.5 text-[0.62rem] text-[var(--muted-foreground)]"
                      title={t("readBackedTitle", { list: row.checked_by_read.join(", ") })}
                    >
                      <SearchCheck className="h-3 w-3" />
                      {t("readBacked", { n: row.checked_by_read.length })}
                    </span>
                  ) : null}
                  {/* Inline, not `ml-auto`: pushed to the far edge it wrapped onto a line of its
                      own and read as a floating fragment, detached from the row it qualifies.
                      It belongs at the end of the same sentence. */}
                  {row.gates_agents && row.state !== "served" ? (
                    <span className="text-[0.66rem] text-[var(--tessera-fg-warning)]">
                      {t("mayBlockAgents")}
                    </span>
                  ) : null}
                  {/* What the silence COSTS — the sentence ADR 0052 requires and the row did
                      not carry. « Suivi des appels au modèle — indécidable » names a capability
                      and leaves the reader to work out what they have stopped being able to
                      answer; this says it. */}
                  <span className="w-full text-[0.62rem] leading-snug text-[var(--muted-foreground)]">
                    {t(`cost.${row.key}`)}
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

"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { useDecimalFormat, useIntFormat, usePercentFormat } from "@/lib/format-number";
import { useEffect, useRef, useState } from "react";

import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { AGENT_SCOPE_ALL } from "@/lib/agent-scope";
import { fetchFleet } from "@/lib/api/client";
import type { Fleet } from "@/lib/api/schemas";
import { COL_IDENTITY, COL_VERDICT, TABLE_BREAKDOWN } from "@/lib/breakdown-columns";

/**
 * Percentages and durations in the reader's language.
 *
 * `.toFixed(1).replace(".", ",")` was right in French and silently wrong for every other
 * operator — and the percent SIGN moves too: French and German space it, English does not, which
 * gluing " %" on by hand cannot know. `pct` takes a percentage (71.6) because that is what the
 * callers hold; Intl wants a ratio, hence the division.
 */
function useFmt() {
  const percent = usePercentFormat(1);
  const decimal = useDecimalFormat(1);
  return {
    pct: (n: number) => percent(n / 100),
    secs: (ms: number | null) => (ms === null ? "—" : `${decimal(ms / 1000)} s`),
  };
}

const RELEASE_TONE: Record<string, string> = {
  good: "text-[var(--tessera-fg-success)]",
  crit: "text-[var(--tessera-fg-danger)]",
  bad: "text-[var(--tessera-fg-warning)]",
  muted: "text-[var(--tessera-text-muted)]",
};

type FleetAgent = NonNullable<Fleet["agents"]>[number];

function rowClass(selected: boolean, dimmed: boolean): string {
  return `border-t border-[var(--tessera-border)] ${selected ? "bg-[#7c5cf5]/10" : ""} ${
    dimmed ? "opacity-45" : ""
  }`;
}

/**
 * The overview's fleet table is an as-of-T client island. Its initial payload is
 * server-rendered for first paint and deep links; later cursor commits read only
 * `/observability/fleet`, instead of rerendering the whole cockpit.
 */
export function TemporalMonitoringBreakdown({
  initialFleet,
  scope,
  locale,
  period,
  at,
  initialPeriod,
  initialAt,
  onTemporalLoadSettled,
}: {
  initialFleet: Fleet | null;
  scope: string;
  locale: string;
  period: string;
  at: string | null;
  initialPeriod: string;
  initialAt: string | null;
  onTemporalLoadSettled?: (at: string) => void;
}) {
  // useTemporalState hydrates from the URL after the first client paint. Keep the
  // server's exact period/T until that mount has happened, so a historical deep
  // link never caches its payload under the temporary live key.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  const effectivePeriod = hydrated ? period : initialPeriod;
  const effectiveAt = hydrated ? at : initialAt;
  const currentKey = `${locale}|${effectivePeriod}|${effectiveAt ?? ""}`;
  const initialKey = useRef(`${locale}|${initialPeriod}|${initialAt ?? ""}`);

  const fleetQuery = useQuery({
    queryKey: ["temporal-monitoring-fleet", locale, effectivePeriod, effectiveAt],
    queryFn: ({ signal }) =>
      fetchFleet(signal, {
        lang: locale,
        period: effectivePeriod,
        at: effectiveAt ?? undefined,
      }),
    initialData: currentKey === initialKey.current ? (initialFleet ?? undefined) : undefined,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
  const settledAt = useRef<string | null>(null);
  useEffect(() => {
    if (effectiveAt == null || fleetQuery.isFetching || settledAt.current === effectiveAt) return;
    settledAt.current = effectiveAt;
    onTemporalLoadSettled?.(effectiveAt);
  }, [effectiveAt, fleetQuery.isFetching, onTemporalLoadSettled]);

  return (
    <MonitoringFleetTable
      fleet={fleetQuery.data ?? initialFleet}
      scope={scope}
      busy={fleetQuery.isPlaceholderData}
      // Without this the table cannot tell a refused or broken read from a real answer of
      // zero, and it renders "no agents" — a statement about the ORGANISATION derived from a
      // fact about the REQUEST. The SSR caller has no query and passes nothing, so it keeps
      // the honest-empty branch it already had.
      failed={fleetQuery.isError && !fleetQuery.data && !initialFleet}
      onRetry={() => void fleetQuery.refetch()}
      retrying={fleetQuery.isFetching}
    />
  );
}

/** Monitoring-lens presentation shared by the initial and temporal payloads. */
export function MonitoringFleetTable({
  fleet,
  scope,
  busy = false,
  failed = false,
  onRetry,
  retrying = false,
}: {
  fleet: Fleet | null;
  scope: string;
  busy?: boolean;
  /** The read failed — distinct from "the read succeeded and there is nothing". */
  failed?: boolean;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const fmtInt = useIntFormat();
  const { pct: fmtPct, secs: fmtSecs } = useFmt();
  const t = useTranslations("agentScope");
  const agents = fleet?.agents ?? [];

  if (failed && onRetry) {
    return <QueryErrorState onRetry={onRetry} retrying={retrying} compact />;
  }

  if (!fleet || agents.length === 0) {
    return (
      <section
        data-testid="fleet-breakdown"
        aria-busy={busy}
        className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4"
      >
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        <p className="mt-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("empty")}</p>
      </section>
    );
  }

  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  const handoffGap = attested - seenShared;

  return (
    <section
      data-testid="fleet-breakdown"
      aria-busy={busy}
      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 transition-opacity aria-busy:opacity-70"
    >
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
      </div>
      <div className="overflow-x-auto">
        <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
          <thead>
            <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
              <th className="pb-2 text-center font-medium">{t("colVolume")}</th>
              <th className="pb-2 text-center font-medium">{t("colEscalation")}</th>
              <th className="pb-2 text-center font-medium">{t("colLatency")}</th>
              <th className="pb-2 text-center font-medium">{t("colHandoffs")}</th>
              {/* Prose, not a number: sized by `COL_VERDICT`, which explains why. */}
              <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>
                {t("colRelease")}
              </th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent: FleetAgent) => {
              const selected = scope !== AGENT_SCOPE_ALL && agent.id === scope;
              const dimmed = scope !== AGENT_SCOPE_ALL && agent.id !== scope;
              return (
                <tr key={agent.id} className={rowClass(selected, dimmed)}>
                  <td className="py-1.5 pr-3 font-medium">{agent.name}</td>
                  <td className="py-1.5 text-center tabular-nums">{fmtInt(agent.conversations)}</td>
                  <td className="py-1.5 text-center tabular-nums">
                    {fmtPct(agent.escalation_rate)}
                  </td>
                  <td className="py-1.5 text-center tabular-nums">{fmtSecs(agent.latency_ms)}</td>
                  <td className="py-1.5 text-center tabular-nums">
                    {agent.handoffs_in} / {agent.handoffs_out}
                  </td>
                  <td className="py-1.5 pr-2 text-right">
                    <span
                      className={
                        RELEASE_TONE[agent.release?.verdict_tone ?? "muted"] ?? RELEASE_TONE.muted
                      }
                    >
                      {agent.release?.available ? agent.release.verdict_label : t("releaseNotRun")}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-[#7c5cf5]/40">
              <td className="py-2 pr-3 font-semibold text-[var(--tessera-fg-accent)]">
                {t("orgTotal")}
              </td>
              <td
                data-testid="fleet-org-total"
                className="py-2 text-center font-semibold tabular-nums text-[var(--tessera-fg-accent)]"
              >
                {fmtInt(fleet.org?.conversations ?? 0)}
              </td>
              <td
                colSpan={4}
                className="py-2 pr-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
                <DedupFooter
                  fleet={fleet}
                  attested={attested}
                  seenShared={seenShared}
                  handoffGap={handoffGap}
                />
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}

function DedupFooter({
  fleet,
  attested,
  seenShared,
  handoffGap,
}: {
  fleet: Fleet;
  attested: number;
  seenShared: number;
  handoffGap: number;
}) {
  const fmtInt = useIntFormat();
  const t = useTranslations("agentScope");
  const total = fmtInt(fleet.org?.conversations ?? 0);

  if (attested === 0) {
    return <span className="block">{t("noHandoffSummary", { total })}</span>;
  }

  if (handoffGap > 0) {
    return (
      <span className="block text-[var(--tessera-fg-warning)]/90">
        {t("handoffGap", {
          events: fmtInt(fleet.handoff_events ?? 0),
          attested: fmtInt(attested),
          seen: fmtInt(seenShared),
        })}
      </span>
    );
  }

  return (
    <span className="block">
      {t(`handoffSummary.${attested === 1 ? "one" : "many"}`, {
        attested: fmtInt(attested),
        total,
      })}
    </span>
  );
}

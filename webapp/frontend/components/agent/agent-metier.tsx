"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  ShieldCheck,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { WorkflowRunsPanel } from "@/components/observability/workflow-runs-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchBusinessCapabilities, fetchBusinessRuns } from "@/lib/api/client";
import type {
  BusinessCapabilitiesResponse,
  BusinessCapabilityRow,
  BusinessSignalValue,
  BusinessTrend,
} from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";

const LEVEL_ORDER = ["runtime", "human_action"];

function pct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number.isInteger(value) ? value : value.toFixed(1)}%`;
}

function count(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString("fr-FR");
}

function trendIcon(direction: string) {
  if (direction === "up") return ArrowUp;
  if (direction === "down") return ArrowDown;
  return ArrowRight;
}

function capabilityMessageKey(row: BusinessCapabilityRow): string | null {
  const key = row.label_key;
  return key?.startsWith("capability.") ? key.slice("capability.".length) : null;
}

function signalGroups(signals: BusinessSignalValue[]): [string, BusinessSignalValue[]][] {
  const byLevel = new Map<string, BusinessSignalValue[]>();
  for (const signal of signals) {
    byLevel.set(signal.level, [...(byLevel.get(signal.level) ?? []), signal]);
  }
  return [...byLevel.entries()].sort(([a], [b]) => {
    const ai = LEVEL_ORDER.indexOf(a);
    const bi = LEVEL_ORDER.indexOf(b);
    if (ai === -1 && bi === -1) return a.localeCompare(b);
    if (ai === -1) return 1;
    if (bi === -1) return -1;
    return ai - bi;
  });
}

export function AgentMetier() {
  const t = useTranslations("agentMetier");
  const tCapability = useTranslations("capability");
  const agentId = useAgentId();
  const [selectedCapabilityId, setSelectedCapabilityId] = useState<string | null>(null);

  const aggregate = useQuery({
    queryKey: ["business-capabilities", agentId],
    queryFn: ({ signal }) => fetchBusinessCapabilities(signal, { agent: agentId }),
    placeholderData: keepPreviousData,
    refetchInterval: 5_000,
  });

  const data = aggregate.data;
  const firstCapabilityId = useMemo(() => {
    const rows = data?.capabilities ?? [];
    return (
      rows.find((row) => row.volume > 0 && capabilityMessageKey(row))?.capability_id ??
      rows.find((row) => capabilityMessageKey(row))?.capability_id ??
      null
    );
  }, [data]);
  const activeCapabilityId = selectedCapabilityId ?? firstCapabilityId;
  const activeCapability =
    data?.capabilities.find((row) => row.capability_id === activeCapabilityId) ?? null;
  const activeCapabilityLabel = activeCapability
    ? capabilityLabel(activeCapability, tCapability)
    : t("runs.allCapabilities");
  const activeCapabilitySelectable = activeCapability
    ? capabilityMessageKey(activeCapability)
    : null;

  const runs = useQuery({
    queryKey: ["business-runs", agentId, activeCapabilityId],
    queryFn: ({ signal }) =>
      fetchBusinessRuns(signal, {
        agent: agentId,
        capabilityId: activeCapabilityId ?? undefined,
        limit: 30,
      }),
    enabled:
      data?.observability_level === "L3" &&
      Boolean(activeCapabilityId && activeCapabilitySelectable),
    placeholderData: keepPreviousData,
    refetchInterval: 5_000,
  });

  if (aggregate.isLoading && !data) return <MetierSkeleton />;

  if (!data || aggregate.isError) {
    return (
      <HonestEmpty
        title={t("unavailable.title")}
        detail={t("unavailable.detail")}
        level={null}
        missing={[]}
      />
    );
  }

  if (data.observability_level !== "L3") {
    return (
      <HonestEmpty
        title={t("empty.title")}
        detail={t("empty.detail")}
        level={data.observability_level ?? null}
        missing={data.missing_requirements}
      />
    );
  }

  return (
    <div className="flex min-w-0 flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <SignalBanner data={data} signals={data.business_signals} />

      <div className="grid min-w-0 gap-2.5 xl:grid-cols-[minmax(0,1fr)_minmax(430px,0.9fr)]">
        <CapabilitiesTable
          capabilities={data.capabilities}
          selectedCapabilityId={activeCapabilityId}
          onSelect={setSelectedCapabilityId}
        />
        <WorkflowRunsPanel
          data={runs.data}
          loading={runs.isLoading}
          title={t("runs.title", { capability: activeCapabilityLabel })}
          emptyTitle={t("runs.emptyTitle")}
          emptyHint={t("runs.emptyHint")}
        />
      </div>
    </div>
  );
}

function capabilityLabel(
  row: BusinessCapabilityRow,
  tCapability: ReturnType<typeof useTranslations>,
) {
  const key = capabilityMessageKey(row);
  if (key && tCapability.has(key)) return tCapability(key);
  return row.label ?? "—";
}

function trendLabel(trend: BusinessTrend, t: ReturnType<typeof useTranslations>): string {
  if (!trend.available) return t("trend.insufficient_data");
  if (trend.direction === "up") return t("trend.up", { delta: trend.delta_pct ?? 0 });
  if (trend.direction === "down") return t("trend.down", { delta: Math.abs(trend.delta_pct ?? 0) });
  return t("trend.flat");
}

function SignalBanner({
  data,
  signals,
}: {
  data: BusinessCapabilitiesResponse;
  signals: BusinessSignalValue[];
}) {
  const t = useTranslations("agentMetier");
  const tSignal = useTranslations("businessSignal");
  const groups = signalGroups(signals);
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BriefcaseBusiness className="h-4 w-4 text-[#b9a6ff]" />
          <h2 className="text-sm font-semibold">{t("signals.title")}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="info">{t("level", { level: data.observability_level ?? "—" })}</Badge>
          <Badge tone="neutral">{t("events", { count: data.event_count })}</Badge>
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-lg border border-[var(--tessera-border)] p-3 text-sm text-[var(--tessera-text-muted)]">
          {t("signals.empty")}
        </div>
      ) : (
        <div className="grid gap-2 xl:grid-cols-2">
          {groups.map(([level, levelSignals]) => (
            <div key={level} className="flex min-w-0 flex-col gap-1.5">
              <div className="text-[0.63rem] font-semibold uppercase tracking-[0.08em] text-[var(--tessera-text-muted)]">
                {t(`signalLevel.${level}`)}
              </div>
              <div className="grid gap-1.5 sm:grid-cols-2">
                {levelSignals.map((signal) => (
                  <SignalTile
                    key={signal.key}
                    signal={signal}
                    label={signalLabel(signal, tSignal)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function signalLabel(signal: BusinessSignalValue, tSignal: ReturnType<typeof useTranslations>) {
  return tSignal.has(signal.key) ? tSignal(signal.key) : "—";
}

function SignalTile({ signal, label }: { signal: BusinessSignalValue; label: string }) {
  const t = useTranslations("agentMetier");
  const TrendIcon = trendIcon(signal.trend.direction);
  const hasValue = typeof signal.value_pct === "number";
  return (
    <div className="min-w-0 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)]/40 p-2">
      <div className="flex items-start justify-between gap-2">
        <span className="line-clamp-2 text-[0.72rem] font-semibold leading-snug">{label}</span>
        {signal.north_star ? <Badge tone="gold">{t("signals.northStar")}</Badge> : null}
      </div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span
          className={cn(
            "text-xl font-semibold",
            hasValue ? "text-[var(--tessera-text)]" : "text-[var(--tessera-text-muted)]",
          )}
        >
          {hasValue ? pct(signal.value_pct) : "—"}
        </span>
        <span className="inline-flex items-center gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
          <TrendIcon className="h-3 w-3" />
          {trendLabel(signal.trend, t)}
        </span>
      </div>
    </div>
  );
}

function CapabilitiesTable({
  capabilities,
  selectedCapabilityId,
  onSelect,
}: {
  capabilities: BusinessCapabilityRow[];
  selectedCapabilityId: string | null;
  onSelect: (capabilityId: string) => void;
}) {
  const t = useTranslations("agentMetier");
  const tCapability = useTranslations("capability");
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <BarChart3 className="h-4 w-4 text-[var(--tessera-green)]" />
          {t("capabilities.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.62rem] uppercase tracking-[0.06em] text-[var(--tessera-text-muted)]">
              <th className="py-2 pr-3 font-semibold">{t("capabilities.columns.capability")}</th>
              <th className="px-3 py-2 text-right font-semibold">
                {t("capabilities.columns.volume")}
              </th>
              <th className="px-3 py-2 text-right font-semibold">
                {t("capabilities.columns.conformity")}
              </th>
              <th className="px-3 py-2 text-right font-semibold">
                {t("capabilities.columns.validation")}
              </th>
              <th className="px-3 py-2 text-right font-semibold">
                {t("capabilities.columns.blocked")}
              </th>
              <th className="px-3 py-2 text-right font-semibold">
                {t("capabilities.columns.prevented")}
              </th>
              <th className="py-2 pl-3 font-semibold">{t("capabilities.columns.trend")}</th>
            </tr>
          </thead>
          <tbody>
            {capabilities.map((row) => {
              const label = capabilityLabel(row, tCapability);
              const selectable = Boolean(capabilityMessageKey(row));
              const selected = row.capability_id === selectedCapabilityId;
              const TrendIcon = trendIcon(row.trend.direction);
              return (
                <tr
                  key={row.capability_id}
                  className={cn(
                    "border-b border-[var(--tessera-border)]/70 transition-colors",
                    selected
                      ? "bg-[var(--tessera-green)]/10"
                      : "hover:bg-[var(--tessera-muted)]/60",
                  )}
                >
                  <td className="py-2 pr-3">
                    <button
                      type="button"
                      disabled={!selectable}
                      onClick={() => onSelect(row.capability_id)}
                      className={cn(
                        "flex min-w-0 items-center gap-2 text-left font-semibold",
                        selectable
                          ? "text-[var(--tessera-text)]"
                          : "cursor-default text-[var(--tessera-text-muted)]",
                      )}
                    >
                      {selected ? (
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
                      ) : (
                        <Activity className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
                      )}
                      <span className="truncate">{label}</span>
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{count(row.volume)}</td>
                  <td className="px-3 py-2 text-right font-mono">{pct(row.conformity_pct)}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {pct(row.validation_required_pct)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{pct(row.blocked_pct)}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {count(row.external_effects_prevented)}
                  </td>
                  <td className="py-2 pl-3">
                    <span className="inline-flex items-center gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
                      <TrendIcon className="h-3 w-3" />
                      {trendLabel(row.trend, t)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

function HonestEmpty({
  title,
  detail,
  level,
  missing,
}: {
  title: string;
  detail: string;
  level: string | null;
  missing: string[];
}) {
  const t = useTranslations("agentMetier");
  return (
    <div className="flex min-h-[54vh] items-center justify-center">
      <Card className="w-full max-w-3xl">
        <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
          <ShieldCheck className="h-8 w-8 text-[var(--tessera-green)]" />
          <div>
            <h2 className="text-base font-semibold">{title}</h2>
            <p className="mt-1 max-w-2xl text-sm text-[var(--tessera-text-muted)]">{detail}</p>
          </div>
          <div className="flex flex-wrap justify-center gap-1.5">
            <Badge tone={level === "L3" ? "success" : "warning"}>
              {t("level", { level: level ?? "—" })}
            </Badge>
            {missing.map((item) => (
              <Badge key={item} tone="neutral">
                {t(`missing.${item}`)}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MetierSkeleton() {
  return (
    <div className="flex flex-col gap-2.5">
      <Skeleton className="h-32 rounded-lg" />
      <div className="grid gap-2.5 xl:grid-cols-[minmax(0,1fr)_minmax(430px,0.9fr)]">
        <Skeleton className="h-[430px] rounded-lg" />
        <Skeleton className="h-[430px] rounded-lg" />
      </div>
    </div>
  );
}

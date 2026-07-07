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
  ChevronRight,
  ShieldCheck,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { type KeyboardEvent, useMemo, useState } from "react";

import { MetricCard } from "@/components/cockpit/metric-card";
import { WorkflowRunsPanel } from "@/components/observability/workflow-runs-panel";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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

function orderedSignals(signals: BusinessSignalValue[]): BusinessSignalValue[] {
  return [...signals].sort((a, b) => {
    const ai = LEVEL_ORDER.indexOf(a.level);
    const bi = LEVEL_ORDER.indexOf(b.level);
    if (a.north_star !== b.north_star) return a.north_star ? -1 : 1;
    if (ai !== bi) {
      return (ai === -1 ? LEVEL_ORDER.length : ai) - (bi === -1 ? LEVEL_ORDER.length : bi);
    }
    return a.key.localeCompare(b.key);
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
      <SignalKpiStrip data={data} signals={data.business_signals} />

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

function SignalKpiStrip({
  data,
  signals,
}: {
  data: BusinessCapabilitiesResponse;
  signals: BusinessSignalValue[];
}) {
  const t = useTranslations("agentMetier");
  const tSignal = useTranslations("businessSignal");
  const ordered = orderedSignals(signals);
  return (
    <section className="flex min-w-0 flex-col gap-2">
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

      {ordered.length === 0 ? (
        <Card>
          <CardContent className="py-3 text-sm text-[var(--tessera-text-muted)]">
            {t("signals.empty")}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
          {ordered.map((signal) => (
            <SignalMetric key={signal.key} signal={signal} label={signalLabel(signal, tSignal)} />
          ))}
        </div>
      )}
    </section>
  );
}

function signalLabel(signal: BusinessSignalValue, tSignal: ReturnType<typeof useTranslations>) {
  return tSignal.has(signal.key) ? tSignal(signal.key) : "—";
}

function signalLevelLabel(signal: BusinessSignalValue, t: ReturnType<typeof useTranslations>) {
  const key = `signalLevel.${signal.level}`;
  return t.has(key) ? t(key) : t("signalLevel.other");
}

function SignalMetric({ signal, label }: { signal: BusinessSignalValue; label: string }) {
  const t = useTranslations("agentMetier");
  const TrendIcon = trendIcon(signal.trend.direction);
  const hasValue = typeof signal.value_pct === "number";
  return (
    <MetricCard
      label={label}
      value={hasValue ? pct(signal.value_pct) : "—"}
      delta={signal.north_star ? <Badge tone="gold">{t("signals.northStar")}</Badge> : null}
      trend={
        <span className="flex min-w-0 items-center justify-between gap-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
          <span className="inline-flex min-w-0 items-center gap-1 truncate">
            <TrendIcon className="h-3 w-3 shrink-0" />
            <span className="truncate">{trendLabel(signal.trend, t)}</span>
          </span>
          <span className="shrink-0">{signalLevelLabel(signal, t)}</span>
        </span>
      }
    />
  );
}

function rowKeyDown(
  event: KeyboardEvent<HTMLTableRowElement>,
  selectable: boolean,
  onSelect: () => void,
) {
  if (!selectable) return;
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    onSelect();
  }
}

function CapabilityName({
  row,
  label,
  selected,
  selectable,
}: {
  row: BusinessCapabilityRow;
  label: string;
  selected: boolean;
  selectable: boolean;
}) {
  return (
    <span
      className={cn(
        "flex min-w-0 items-center gap-2 font-semibold",
        selectable ? "text-[var(--tessera-text)]" : "text-[var(--tessera-text-muted)]",
      )}
    >
      {selected ? (
        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
      ) : (
        <Activity className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
      )}
      <span className="truncate">{label}</span>
      {selectable ? (
        <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
      ) : null}
      <span className="sr-only">{row.capability_id}</span>
    </span>
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
    <Card className="flex min-w-0 flex-col overflow-hidden">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 font-sans text-[0.82rem] font-medium tracking-normal">
          <BarChart3 className="h-4 w-4 text-[var(--tessera-green)]" />
          {t("capabilities.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="min-w-0 p-0">
        <Table className="min-w-[760px] text-[0.72rem]">
          <TableHeader>
            <TableRow>
              <TableHead className="h-8 px-3 text-[0.6rem]">
                {t("capabilities.columns.capability")}
              </TableHead>
              <TableHead className="h-8 px-3 text-right text-[0.6rem]">
                {t("capabilities.columns.volume")}
              </TableHead>
              <TableHead className="h-8 px-3 text-right text-[0.6rem]">
                {t("capabilities.columns.conformity")}
              </TableHead>
              <TableHead className="h-8 px-3 text-right text-[0.6rem]">
                {t("capabilities.columns.validation")}
              </TableHead>
              <TableHead className="h-8 px-3 text-right text-[0.6rem]">
                {t("capabilities.columns.blocked")}
              </TableHead>
              <TableHead className="h-8 px-3 text-right text-[0.6rem]">
                {t("capabilities.columns.prevented")}
              </TableHead>
              <TableHead className="h-8 px-3 text-[0.6rem]">
                {t("capabilities.columns.trend")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {capabilities.map((row) => {
              const label = capabilityLabel(row, tCapability);
              const selectable = Boolean(capabilityMessageKey(row));
              const selected = row.capability_id === selectedCapabilityId;
              const TrendIcon = trendIcon(row.trend.direction);
              const selectRow = () => onSelect(row.capability_id);
              return (
                <TableRow
                  key={row.capability_id}
                  data-state={selected ? "selected" : undefined}
                  role={selectable ? "button" : undefined}
                  tabIndex={selectable ? 0 : undefined}
                  onClick={selectable ? selectRow : undefined}
                  onKeyDown={(event) => rowKeyDown(event, selectable, selectRow)}
                  className={cn(
                    "border-[var(--tessera-border)]/50",
                    selectable ? "cursor-pointer" : "cursor-default hover:bg-transparent",
                    selected && "bg-[var(--tessera-muted)]/60",
                  )}
                >
                  <TableCell className="px-3 py-2">
                    <CapabilityName
                      row={row}
                      label={label}
                      selected={selected}
                      selectable={selectable}
                    />
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right font-mono">
                    {count(row.volume)}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right font-mono">
                    {pct(row.conformity_pct)}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right font-mono">
                    {pct(row.validation_required_pct)}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right font-mono">
                    {pct(row.blocked_pct)}
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right font-mono">
                    {count(row.external_effects_prevented)}
                  </TableCell>
                  <TableCell className="px-3 py-2">
                    <span className="inline-flex items-center gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
                      <TrendIcon className="h-3 w-3 shrink-0" />
                      {trendLabel(row.trend, t)}
                    </span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
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
  const badges = (
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
  );
  return (
    <div className="flex min-h-[54vh] items-center justify-center">
      <Card className="w-full max-w-3xl">
        <CardContent className="p-3">
          <EmptyState
            icon={<ShieldCheck />}
            title={title}
            description={detail}
            action={badges}
            className="border-[var(--tessera-border)] bg-[var(--tessera-bg)]/30 py-8"
          />
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

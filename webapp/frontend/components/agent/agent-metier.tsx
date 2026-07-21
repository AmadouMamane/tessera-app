"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BarChart3,
  BriefcaseBusiness,
  CheckCircle2,
  ChevronRight,
  Clock,
  Radio,
  ShieldCheck,
  Target,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { type KeyboardEvent, useCallback, useMemo } from "react";

import { CardInfo } from "@/components/cockpit/card-info";
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
import { Truncate } from "@/components/ui/truncate";
import { usePathname, useRouter } from "@/i18n/navigation";
import { fetchBusinessCapabilities, fetchBusinessRuns } from "@/lib/api/client";
import type {
  BusinessCapabilitiesResponse,
  BusinessCapabilityRow,
  BusinessSignalValue,
  BusinessTrend,
} from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { metierTemporalMode, resolveMetierAsOf } from "@/lib/metier-temporal";
import { getTemporalContext } from "@/lib/temporal-context";
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

function groupedSignals(signals: BusinessSignalValue[]): [string, BusinessSignalValue[]][] {
  const groups = new Map<string, BusinessSignalValue[]>();
  for (const signal of signals) {
    const current = groups.get(signal.level) ?? [];
    current.push(signal);
    groups.set(signal.level, current);
  }
  return Array.from(groups.entries());
}

export function AgentMetier() {
  const t = useTranslations("agentMetier");
  const tCapability = useTranslations("capability");
  const agentId = useAgentId();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const requestedCapabilityId = searchParams.get("capability_id");
  const requestedTurnId = searchParams.get("turn_id");
  // BR-01 §5: the temporal read is the global as-of instant — URL is the source of truth
  // (deep-link); the shared cockpit context follows the user across pages. Live by default.
  const asOf =
    resolveMetierAsOf({ asof: searchParams.get("asof"), at: searchParams.get("at") }) ??
    getTemporalContext().asOf;

  // BR-01 §5: capability + run selection derive from the URL (deep-link), never local state.
  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null) params.delete(key);
        else params.set(key, value);
      }
      router.replace({ pathname, query: Object.fromEntries(params.entries()) }, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  const aggregate = useQuery({
    queryKey: ["business-capabilities", agentId, asOf],
    queryFn: ({ signal }) =>
      fetchBusinessCapabilities(signal, { agent: agentId, at: asOf ?? undefined }),
    placeholderData: keepPreviousData,
    refetchInterval: asOf ? false : 5_000,
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
  const queryCapabilityId =
    requestedCapabilityId &&
    data?.capabilities.some((row) => row.capability_id === requestedCapabilityId)
      ? requestedCapabilityId
      : null;
  const activeCapabilityId = queryCapabilityId ?? firstCapabilityId;
  const activeCapability =
    data?.capabilities.find((row) => row.capability_id === activeCapabilityId) ?? null;
  const activeCapabilityLabel = activeCapability
    ? capabilityLabel(activeCapability, tCapability)
    : t("runs.allCapabilities");
  const activeCapabilitySelectable = activeCapability
    ? capabilityMessageKey(activeCapability)
    : null;

  const runs = useQuery({
    queryKey: ["business-runs", agentId, activeCapabilityId, asOf],
    queryFn: ({ signal }) =>
      fetchBusinessRuns(signal, {
        agent: agentId,
        capabilityId: activeCapabilityId ?? undefined,
        limit: 30,
        at: asOf ?? undefined,
      }),
    enabled:
      data?.observability_level === "L3" &&
      Boolean(activeCapabilityId && activeCapabilitySelectable),
    placeholderData: keepPreviousData,
    refetchInterval: asOf ? false : 5_000,
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
      <SignalKpiStrip data={data} signals={data.business_signals} asOf={asOf} />

      <CapabilitiesTable
        capabilities={data.capabilities}
        selectedCapabilityId={activeCapabilityId}
        onSelect={(capabilityId) => updateParams({ capability_id: capabilityId, turn_id: null })}
      />

      {activeCapabilityId && activeCapabilitySelectable ? (
        <WorkflowRunsPanel
          data={runs.data}
          loading={runs.isLoading}
          title={t("runs.title", { capability: activeCapabilityLabel })}
          emptyTitle={t("runs.emptyTitle")}
          emptyHint={t("runs.emptyHint")}
          selectedTurnId={requestedTurnId}
          onSelectTurn={(turnId) => updateParams({ turn_id: turnId })}
        />
      ) : null}
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

function TrendHint({ trend }: { trend: BusinessTrend }) {
  const t = useTranslations("agentMetier");
  if (!trend.available) {
    return (
      <span
        className="inline-flex h-5 min-w-5 items-center justify-center text-[0.68rem] text-[var(--tessera-text-muted)]"
        title={trendLabel(trend, t)}
      >
        —
      </span>
    );
  }
  const TrendIcon = trendIcon(trend.direction);
  return (
    <span className="inline-flex min-w-0 items-center gap-1 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <TrendIcon className="h-3 w-3 shrink-0" />
      <Truncate full={trendLabel(trend, t)}>{trendLabel(trend, t)}</Truncate>
    </span>
  );
}

function formatAsOf(iso: string): string {
  const stamp = Date.parse(iso);
  if (Number.isNaN(stamp)) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(stamp));
}

function TemporalModeBadge({ asOf }: { asOf: string | null }) {
  const t = useTranslations("agentMetier");
  if (metierTemporalMode(asOf) === "live") {
    return (
      <Badge tone="success">
        <span className="inline-flex items-center gap-1">
          <Radio className="h-3 w-3" />
          {t("temporal.live")}
        </span>
      </Badge>
    );
  }
  return (
    <Badge tone="gold">
      <span className="inline-flex items-center gap-1">
        <Clock className="h-3 w-3" />
        {t("temporal.asOf", { instant: formatAsOf(asOf ?? "") })}
      </span>
    </Badge>
  );
}

function SignalKpiStrip({
  data,
  signals,
  asOf,
}: {
  data: BusinessCapabilitiesResponse;
  signals: BusinessSignalValue[];
  asOf: string | null;
}) {
  const t = useTranslations("agentMetier");
  const tSignal = useTranslations("businessSignal");
  const ordered = orderedSignals(signals);
  const northStar = ordered.find((signal) => signal.north_star) ?? ordered[0] ?? null;
  const secondary = northStar ? ordered.filter((signal) => signal.key !== northStar.key) : ordered;
  const groups = groupedSignals(secondary);
  return (
    <section className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <BriefcaseBusiness className="h-4 w-4 text-[#b9a6ff]" />
          <h2 className="text-sm font-semibold">{t("signals.title")}</h2>
          <CardInfo ns="agentMetier" k="signals" title={t("signals.title")} />
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <TemporalModeBadge asOf={asOf} />
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
        <div className="grid gap-2.5 xl:grid-cols-[minmax(230px,1fr)_minmax(0,4fr)]">
          {northStar ? (
            <NorthStarSignal signal={northStar} label={signalLabel(northStar, tSignal)} />
          ) : null}
          <div className="flex min-w-0 flex-col gap-2">
            {groups.map(([level, levelSignals]) => (
              <SignalGroup key={level} level={level} signals={levelSignals} tSignal={tSignal} />
            ))}
          </div>
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

/** `il y a 3 h` from a real ISO stamp; `null` when there is nothing to date. */
function agoLabel(iso: string | null | undefined, locale: string): string | null {
  if (!iso) return null;
  const stamp = Date.parse(iso);
  if (Number.isNaN(stamp)) return null;
  const minutes = Math.round((Date.now() - stamp) / 60_000);
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (minutes < 60) return rtf.format(-Math.max(minutes, 0), "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return rtf.format(-hours, "hour");
  return rtf.format(-Math.round(hours / 24), "day");
}

/**
 * The hero card, P3 item 18. Three readings, and the dash belongs to exactly one of them:
 *
 *  - **decisive** — a scored value. Show it big, and say what it rests on: `1 vérification ·
 *    dernier contrôle il y a 3 h`. A 100% backed by one check out of 24 runs is a fact the
 *    operator deserves next to the number, not two clicks away.
 *  - **accumulating** — runs were observed but none was scorable yet. Show what we know
 *    (`24 exécutions observées · aucun contrôle applicable`), never a fabricated percentage.
 *  - **zero data** — nothing observed at all. The dash + reason, untouched, as it must be.
 */
function NorthStarSignal({ signal, label }: { signal: BusinessSignalValue; label: string }) {
  const t = useTranslations("agentMetier");
  const locale = useLocale();
  const hasValue = typeof signal.value_pct === "number";
  const evidence = signal.evidence;
  const observedRuns = evidence?.observed_runs ?? 0;
  const checks = evidence?.checks ?? 0;
  const ago = agoLabel(evidence?.last_checked_at, locale);

  const provenance: string[] = [];
  if (hasValue && checks > 0) provenance.push(t("hero.checks", { count: checks }));
  else if (observedRuns > 0) {
    provenance.push(t("hero.observedRuns", { count: observedRuns }));
    if (checks === 0) provenance.push(t("hero.neverChecked"));
  }
  if (ago && (hasValue || observedRuns > 0)) provenance.push(t("hero.lastCheck", { ago }));

  return (
    <Card className="min-w-0 border-[#7c5cf5]/45 bg-[#211d45]/45">
      <CardContent className="flex h-full min-h-[108px] flex-col justify-between p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="mb-1 flex items-center gap-1.5 text-[0.64rem] font-medium uppercase tracking-wide text-[#c4b5fd]">
              <Target className="h-3.5 w-3.5" />
              {t("signals.northStar")}
              <CardInfo ns="agentMetier" k="northStar" title={label} />
            </div>
            <p className="text-sm font-semibold leading-snug">{label}</p>
          </div>
          <Badge tone="gold">{signalLevelLabel(signal, t)}</Badge>
        </div>
        <div className="flex items-end justify-between gap-2">
          {hasValue ? (
            <p className="text-[1.75rem] font-semibold leading-none text-white">
              {pct(signal.value_pct)}
            </p>
          ) : observedRuns > 0 ? (
            // Not decisive, but not empty either: name the state instead of drawing a dash.
            <p className="text-[1.05rem] font-semibold leading-none text-[#c4b5fd]">
              {t("hero.accumulating")}
            </p>
          ) : (
            <p className="text-[1.75rem] font-semibold leading-none text-white">—</p>
          )}
          <TrendHint trend={signal.trend} />
        </div>
        {provenance.length > 0 ? (
          <p className="text-[0.64rem] leading-snug text-[#cfc6ff]">{provenance.join(" · ")}</p>
        ) : null}
        <p className="text-[0.64rem] leading-snug text-[var(--tessera-text-muted)]">
          {signal.reason.replaceAll("_", " ")}
        </p>
      </CardContent>
    </Card>
  );
}

function SignalGroup({
  level,
  signals,
  tSignal,
}: {
  level: string;
  signals: BusinessSignalValue[];
  tSignal: ReturnType<typeof useTranslations>;
}) {
  const t = useTranslations("agentMetier");
  if (signals.length === 0) return null;
  const pseudoSignal = signals[0];
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span className="flex items-center gap-1 font-medium">
          {pseudoSignal ? signalLevelLabel(pseudoSignal, t) : level}
          <CardInfo
            ns="agentMetier"
            k={`level.${level}`}
            title={pseudoSignal ? signalLevelLabel(pseudoSignal, t) : level}
          />
        </span>
        <span>{signals.length}</span>
      </div>
      <div className="grid min-w-0 grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
        {signals.map((signal) => (
          <SignalMetric key={signal.key} signal={signal} label={signalLabel(signal, tSignal)} />
        ))}
      </div>
    </div>
  );
}

function SignalMetric({ signal, label }: { signal: BusinessSignalValue; label: string }) {
  const hasValue = typeof signal.value_pct === "number";
  return (
    <MetricCard
      label={label}
      value={hasValue ? pct(signal.value_pct) : "—"}
      delta={signal.status === "unknown" ? <Badge tone="neutral">—</Badge> : null}
      trend={<TrendHint trend={signal.trend} />}
      info={<CardInfo ns="agentMetier" k={`signal.${signal.key}`} title={label} />}
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
      ) : null}
      <span className="min-w-0 leading-snug">{label}</span>
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
          <CardInfo ns="agentMetier" k="capabilities" title={t("capabilities.title")} />
        </CardTitle>
      </CardHeader>
      <CardContent className="min-w-0 overflow-hidden p-0">
        <Table className="w-full table-fixed text-[0.72rem]">
          <TableHeader>
            <TableRow>
              <TableHead className="h-8 w-[32%] px-3 text-[0.6rem]">
                {t("capabilities.columns.capability")}
              </TableHead>
              <TableHead className="h-8 w-[10%] px-3 text-right text-[0.6rem]">
                <span className="inline-flex items-center justify-end gap-1">
                  {t("capabilities.columns.volume")}
                  <CardInfo
                    ns="agentMetier"
                    k="col.volume"
                    title={t("capabilities.columns.volume")}
                  />
                </span>
              </TableHead>
              <TableHead className="h-8 w-[12%] px-3 text-right text-[0.6rem]">
                <span className="inline-flex items-center justify-end gap-1">
                  {t("capabilities.columns.conformity")}
                  <CardInfo
                    ns="agentMetier"
                    k="col.conformity"
                    title={t("capabilities.columns.conformity")}
                  />
                </span>
              </TableHead>
              <TableHead className="hidden h-8 w-[12%] px-3 text-right text-[0.6rem] md:table-cell">
                <span className="inline-flex items-center justify-end gap-1">
                  {t("capabilities.columns.validation")}
                  <CardInfo
                    ns="agentMetier"
                    k="col.validation"
                    title={t("capabilities.columns.validation")}
                  />
                </span>
              </TableHead>
              <TableHead className="hidden h-8 w-[10%] px-3 text-right text-[0.6rem] lg:table-cell">
                <span className="inline-flex items-center justify-end gap-1">
                  {t("capabilities.columns.blocked")}
                  <CardInfo
                    ns="agentMetier"
                    k="col.blocked"
                    title={t("capabilities.columns.blocked")}
                  />
                </span>
              </TableHead>
              <TableHead className="hidden h-8 w-[12%] px-3 text-right text-[0.6rem] md:table-cell">
                <span className="inline-flex items-center justify-end gap-1">
                  {t("capabilities.columns.prevented")}
                  <CardInfo
                    ns="agentMetier"
                    k="col.prevented"
                    title={t("capabilities.columns.prevented")}
                  />
                </span>
              </TableHead>
              <TableHead className="h-8 w-[12%] px-3 text-[0.6rem]">
                {t("capabilities.columns.trend")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {capabilities.map((row) => {
              const label = capabilityLabel(row, tCapability);
              const selectable = Boolean(capabilityMessageKey(row));
              const selected = row.capability_id === selectedCapabilityId;
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
                  <TableCell className="px-3 py-2 align-middle">
                    <CapabilityName
                      row={row}
                      label={label}
                      selected={selected}
                      selectable={selectable}
                    />
                  </TableCell>
                  <TableCell className="px-3 py-2 text-right font-mono align-middle">
                    {count(row.volume)}
                  </TableCell>
                  <PercentCell value={row.conformity_pct} tone="conformity" />
                  <PercentCell
                    value={row.validation_required_pct}
                    tone="neutral"
                    className="hidden md:table-cell"
                  />
                  <PercentCell
                    value={row.blocked_pct}
                    tone="blocked"
                    className="hidden lg:table-cell"
                  />
                  <TableCell className="hidden px-3 py-2 text-right font-mono align-middle md:table-cell">
                    {count(row.external_effects_prevented)}
                  </TableCell>
                  <TableCell className="px-3 py-2 align-middle">
                    <TrendHint trend={row.trend} />
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

/**
 * A percentage cell with a discreet micro-bar behind it (P3 item 19).
 *
 * The bar IS the value — width is the percentage, so it can never disagree with the number
 * beside it. A null percentage draws no bar at all: an empty track would read as 0%, which is
 * a different claim from "not measured". The tint is on the text, never a badge: `conformity`
 * greens only at 100 and reds below 90; `blocked` is inverted (blocking is the safe outcome);
 * `neutral` never tints. Both tints sit above AA on the surface they render on (item 22).
 */
function PercentCell({
  value,
  tone,
  className,
}: {
  value: number | null | undefined;
  tone: "conformity" | "blocked" | "neutral";
  className?: string;
}) {
  const known = typeof value === "number";
  const text =
    !known || tone === "neutral"
      ? "text-[var(--tessera-text)]"
      : tone === "conformity"
        ? value >= 100
          ? "text-[#7ee2a8]"
          : value < 90
            ? "text-[#ff9d9d]"
            : "text-[var(--tessera-text)]"
        : value > 0
          ? "text-[#7ee2a8]"
          : "text-[var(--tessera-text)]";
  const bar =
    tone === "blocked"
      ? "bg-[#7ee2a8]/18"
      : tone === "conformity"
        ? "bg-[#7c5cf5]/28"
        : "bg-[var(--tessera-border)]/60";

  return (
    <TableCell className={cn("relative px-3 py-2 text-right font-mono align-middle", className)}>
      {known ? (
        <span
          aria-hidden
          className={cn("pointer-events-none absolute inset-y-1 right-1 rounded-sm", bar)}
          style={{ width: `calc(${Math.max(0, Math.min(100, value))}% - 0.5rem)` }}
        />
      ) : null}
      <span className={cn("relative", text)}>{pct(value)}</span>
    </TableCell>
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
      <Skeleton className="h-[320px] rounded-lg" />
      <Skeleton className="h-[460px] rounded-lg" />
    </div>
  );
}

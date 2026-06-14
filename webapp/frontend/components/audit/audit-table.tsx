"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Copy,
  Database,
  ExternalLink,
  FileJson,
  Filter,
  Hash,
  KeyRound,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  X,
} from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { DeltaBadge, MetricCard } from "@/components/cockpit/metric-card";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchAudit, fetchAuditOverview } from "@/lib/api/client";
import type {
  AuditActorRole,
  AuditEntry,
  AuditEventType,
  AuditMetric,
  AuditOutcome,
  AuditOverview,
} from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const PAGE_SIZE = 9;
const OUTCOMES: ReadonlyArray<AuditOutcome> = ["allowed", "denied", "error"];
const EVENT_TYPES: ReadonlyArray<AuditEventType> = ["guard", "tool", "memory", "other"];
const ACTOR_ROLES: ReadonlyArray<AuditActorRole> = ["human", "service", "system", "model"];
const ACTOR_ROLE_SET = new Set<string>(ACTOR_ROLES);
const PERIODS = ["24h", "7d", "30d"] as const;

type Period = (typeof PERIODS)[number];
type SelectValueState = "all" | string;

interface AuditWindow {
  preset: Period;
  since: string;
  until: string;
}

function makeWindow(preset: Period, anchor: Date = new Date()): AuditWindow {
  const until = anchor;
  const hours = preset === "24h" ? 24 : preset === "7d" ? 24 * 7 : 24 * 30;
  const since = new Date(until.getTime() - hours * 60 * 60 * 1000);
  return { preset, since: since.toISOString(), until: until.toISOString() };
}

function endOfLocalDay(value: string): Date | null {
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 23, 59, 59, 999);
}

function dateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfLocalMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addLocalMonths(date: Date, amount: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function calendarMonthDays(month: Date): Date[] {
  const first = startOfLocalMonth(month);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first);
  start.setDate(first.getDate() - mondayOffset);
  return Array.from(
    { length: 42 },
    (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index),
  );
}

function isSameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

export function AuditTable({ initialWindow }: { initialWindow?: AuditWindow }) {
  const t = useTranslations("audit");
  const tCommon = useTranslations("common");
  const formatter = useFormatter();
  const locale = useLocale();
  const numberFormatter = useMemo(() => new Intl.NumberFormat(locale), [locale]);

  const [cursor, setCursor] = useState(0);
  const [window, setWindow] = useState<AuditWindow>(() => initialWindow ?? makeWindow("7d"));
  const [query, setQuery] = useState("");
  const [outcome, setOutcome] = useState<AuditOutcome | "all">("all");
  const [eventType, setEventType] = useState<AuditEventType | "all">("all");
  const [actorRole, setActorRole] = useState<AuditActorRole | "all">("all");
  const [scope, setScope] = useState<SelectValueState>("all");
  const [selected, setSelected] = useState<AuditEntry | null>(null);

  const filters = useMemo(
    () => ({
      outcome: outcome === "all" ? undefined : outcome,
      eventType: eventType === "all" ? undefined : eventType,
      actorRole: actorRole === "all" ? undefined : actorRole,
      scope: scope === "all" ? undefined : scope,
      query: query.trim() || undefined,
      since: window.since,
      until: window.until,
    }),
    [actorRole, eventType, outcome, query, scope, window.since, window.until],
  );

  const overview = useQuery({
    queryKey: ["audit-overview", filters],
    queryFn: ({ signal }) => fetchAuditOverview({ ...filters, signal }),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const page = useQuery({
    queryKey: ["audit", cursor, filters],
    queryFn: ({ signal }) =>
      fetchAudit({
        ...filters,
        cursor,
        limit: PAGE_SIZE,
        signal,
      }),
    placeholderData: (prev) => prev,
    staleTime: 30_000,
  });

  const entries = page.data?.entries ?? [];
  const selectedKey = selected ? entryKey(selected) : null;

  useEffect(() => {
    if (selected && !entries.some((entry) => entryKey(entry) === selectedKey)) {
      setSelected(null);
    }
  }, [entries, selected, selectedKey]);

  function applyPeriod(period: Period) {
    setCursor(0);
    setWindow(makeWindow(period));
  }

  function applyDate(value: string) {
    const end = endOfLocalDay(value);
    if (!end) return;
    setCursor(0);
    setWindow(makeWindow(window.preset, end));
  }

  function resetPaging(update: () => void) {
    setCursor(0);
    update();
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col gap-3 overflow-hidden text-[var(--tessera-text)]">
      <PeriodRail
        value={window.preset}
        overview={overview.data}
        loading={overview.isLoading}
        onPeriod={applyPeriod}
        onDate={applyDate}
      />

      <MetricGrid
        overview={overview.data}
        loading={overview.isLoading}
        formatter={numberFormatter}
      />

      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full min-h-0 flex-col gap-3 overflow-hidden">
          <FilterDeck
            overview={overview.data}
            query={query}
            outcome={outcome}
            eventType={eventType}
            actorRole={actorRole}
            scope={scope}
            onQuery={(value) => resetPaging(() => setQuery(value))}
            onOutcome={(value) => resetPaging(() => setOutcome(value))}
            onEventType={(value) => resetPaging(() => setEventType(value))}
            onActorRole={(value) => resetPaging(() => setActorRole(value))}
            onScope={(value) => resetPaging(() => setScope(value))}
          />

          <EventTypeTabs
            overview={overview.data}
            value={eventType}
            onValue={(value) => resetPaging(() => setEventType(value))}
          />

          <section className="min-h-[260px] flex-1 overflow-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
            {page.isPending ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: PAGE_SIZE }).map((_, index) => (
                  <Skeleton
                    // biome-ignore lint/suspicious/noArrayIndexKey: fixed loading placeholders never reorder
                    key={index}
                    className="h-9 w-full"
                  />
                ))}
              </div>
            ) : entries.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={<ShieldCheck />}
                  title={tCommon("empty")}
                  description={t("description")}
                />
              </div>
            ) : (
              <AuditEventsTable
                entries={entries}
                selected={selected}
                onSelect={setSelected}
                formatter={formatter}
              />
            )}
            <Pagination
              cursor={cursor}
              pageSize={PAGE_SIZE}
              hasMore={page.data?.has_more ?? false}
              total={overview.data?.total_events}
              onPrevious={() => setCursor((value) => Math.max(0, value - PAGE_SIZE))}
              onNext={() => setCursor((value) => value + PAGE_SIZE)}
            />
          </section>

          <BottomPanels overview={overview.data} loading={overview.isLoading} />
        </div>
      </div>

      <AuditFooter overview={overview.data} formatter={formatter} />

      {selected ? (
        <AuditDetailOverlay
          entry={selected}
          overview={overview.data}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}

function PeriodRail({
  value,
  overview,
  loading,
  onPeriod,
  onDate,
}: {
  value: Period;
  overview: AuditOverview | undefined;
  loading: boolean;
  onPeriod: (period: Period) => void;
  onDate: (value: string) => void;
}) {
  const t = useTranslations("audit");
  const formatter = useFormatter();
  const locale = useLocale();
  const pickerRef = useRef<HTMLDivElement>(null);
  const selectedDate = useMemo(
    () => (overview?.window_end ? new Date(overview.window_end) : new Date()),
    [overview?.window_end],
  );
  const [pickerOpen, setPickerOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => startOfLocalMonth(selectedDate));
  const monthDays = useMemo(() => calendarMonthDays(calendarMonth), [calendarMonth]);
  const monthFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }),
    [locale],
  );
  const dayFormatter = useMemo(
    () => new Intl.DateTimeFormat(locale, { dateStyle: "full" }),
    [locale],
  );
  const weekdayLabels = useMemo(() => {
    const monday = new Date(2026, 5, 1);
    const weekdayFormatter = new Intl.DateTimeFormat(locale, { weekday: "narrow" });
    return Array.from({ length: 7 }, (_, index) => {
      const day = new Date(2026, 5, monday.getDate() + index);
      return { key: dateInputValue(day), label: weekdayFormatter.format(day) };
    });
  }, [locale]);

  useEffect(() => {
    if (pickerOpen) setCalendarMonth(startOfLocalMonth(selectedDate));
  }, [pickerOpen, selectedDate]);

  useEffect(() => {
    if (!pickerOpen) return;

    function closeOnOutsidePointer(event: MouseEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) setPickerOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setPickerOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [pickerOpen]);

  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="min-w-16 text-xs font-medium text-[var(--tessera-text-muted)]">
        {t("window.label")}
      </span>
      <div className="flex h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]">
        {PERIODS.map((period) => (
          <button
            key={period}
            type="button"
            onClick={() => onPeriod(period)}
            className={cn(
              "h-7 rounded px-3 text-xs font-medium transition-colors",
              value === period
                ? "bg-[#123e6a] text-[#d8eaff] ring-1 ring-[#2e72d2]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {t(`window.${period}`)}
          </button>
        ))}
      </div>
      <div className="flex h-9 max-w-[520px] shrink-0 items-center gap-3 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]">
        <CalendarDays className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
        {loading || !overview ? (
          <Skeleton className="h-4 w-64" />
        ) : (
          <span className="truncate whitespace-nowrap">
            {formatter.dateTime(new Date(overview.window_start), {
              dateStyle: "medium",
              timeStyle: "short",
            })}
            <span className="px-3 text-[var(--tessera-text-muted)]">→</span>
            {formatter.dateTime(new Date(overview.window_end), {
              dateStyle: "medium",
              timeStyle: "short",
            })}
          </span>
        )}
      </div>
      <div ref={pickerRef} className="relative">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={pickerOpen}
          onClick={() => setPickerOpen((open) => !open)}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 font-medium text-[var(--tessera-text-muted)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
        >
          <CalendarDays className="h-4 w-4" />
          {t("window.refresh")}
        </Button>
        {pickerOpen ? (
          <div className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-[292px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[var(--tessera-text)] shadow-[0_20px_60px_rgba(0,0,0,0.38)]">
            <div className="mb-3 flex items-center justify-between border-b border-[var(--tessera-border)] pb-2">
              <button
                type="button"
                aria-label={t("window.previousMonth")}
                onClick={() => setCalendarMonth((month) => addLocalMonths(month, -1))}
                className="grid h-8 w-8 place-items-center rounded-md border border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <p className="text-sm font-semibold capitalize">
                {monthFormatter.format(calendarMonth)}
              </p>
              <button
                type="button"
                aria-label={t("window.nextMonth")}
                onClick={() => setCalendarMonth((month) => addLocalMonths(month, 1))}
                className="grid h-8 w-8 place-items-center rounded-md border border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <div className="grid grid-cols-7 gap-1 text-center text-[0.68rem] font-medium uppercase text-[var(--tessera-text-muted)]">
              {weekdayLabels.map((day) => (
                <span key={day.key}>{day.label}</span>
              ))}
            </div>
            <div className="mt-2 grid grid-cols-7 gap-1">
              {monthDays.map((day) => {
                const inMonth = day.getMonth() === calendarMonth.getMonth();
                const selected = isSameLocalDate(day, selectedDate);
                return (
                  <button
                    key={dateInputValue(day)}
                    type="button"
                    aria-label={dayFormatter.format(day)}
                    onClick={() => {
                      onDate(dateInputValue(day));
                      setPickerOpen(false);
                    }}
                    className={cn(
                      "h-8 rounded-md text-xs font-medium transition-colors",
                      selected
                        ? "bg-[#123e6a] text-[#d8eaff] ring-1 ring-[#2e72d2]"
                        : "text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]",
                      !inMonth && "text-[var(--tessera-text-muted)] opacity-45",
                    )}
                  >
                    {day.getDate()}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function MetricGrid({
  overview,
  loading,
  formatter,
}: {
  overview: AuditOverview | undefined;
  loading: boolean;
  formatter: Intl.NumberFormat;
}) {
  const t = useTranslations("audit.metrics");
  const td = useTranslations("audit.delta");
  const metrics = useMemo(
    () => new Map(overview?.metrics.map((metric) => [metric.key, metric])),
    [overview],
  );
  const series = overview?.timeline.map((bucket) => bucket.total) ?? [];
  const cards: AuditMetric["key"][] = [
    "signed_events",
    "sensitive_actions",
    "guard_refusals",
    "proof_events",
    "chain_integrity",
    "unique_actors",
  ];
  return (
    <div className="grid shrink-0 grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
      {cards.map((key) => {
        const metric = metrics.get(key);
        const chainOk = metric?.value === 1;
        const trend =
          key === "chain_integrity" ? (
            <div className="flex items-center gap-2 text-xs text-[var(--tessera-text-muted)]">
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  chainOk ? "bg-[var(--tessera-green)]" : "bg-red-400",
                )}
              />
              {t(chainOk ? "chainHint" : "chainBrokenHint")}
            </div>
          ) : (
            <MetricSparkline
              className="h-5"
              values={series}
              tone={key === "guard_refusals" ? "danger" : "success"}
            />
          );
        return (
          <MetricCard
            key={key}
            label={t(`${key}.label`)}
            loading={loading || !metric}
            value={
              metric && key === "chain_integrity"
                ? t(metric.value === 1 ? "conform" : "broken")
                : metric
                  ? formatter.format(metric.value)
                  : ""
            }
            delta={
              metric ? <DeltaBadge deltaPct={metric.delta_pct} noneLabel={td("none")} /> : undefined
            }
            trend={trend}
          />
        );
      })}
    </div>
  );
}

function FilterDeck({
  overview,
  query,
  outcome,
  eventType,
  actorRole,
  scope,
  onQuery,
  onOutcome,
  onEventType,
  onActorRole,
  onScope,
}: {
  overview: AuditOverview | undefined;
  query: string;
  outcome: AuditOutcome | "all";
  eventType: AuditEventType | "all";
  actorRole: AuditActorRole | "all";
  scope: SelectValueState;
  onQuery: (value: string) => void;
  onOutcome: (value: AuditOutcome | "all") => void;
  onEventType: (value: AuditEventType | "all") => void;
  onActorRole: (value: AuditActorRole | "all") => void;
  onScope: (value: SelectValueState) => void;
}) {
  const t = useTranslations("audit");
  const tCommon = useTranslations("common");
  return (
    <section className="shrink-0 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1.5">
      <div className="flex items-center gap-2 border-b border-[var(--tessera-border)] px-2 pb-1.5">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
          <Input
            type="search"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder={t("filters.search")}
            aria-label={t("filters.search")}
            className="h-8 border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 text-xs"
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          className="border-[var(--tessera-border)] bg-[var(--tessera-bg)]"
        >
          <Filter className="h-4 w-4" />
          {t("filters.button")}
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-2 px-2 pt-1.5 lg:grid-cols-4">
        <Select
          value={actorRole}
          onValueChange={(value) => onActorRole(value as AuditActorRole | "all")}
        >
          <SelectTrigger className="h-10 border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-xs [&>span]:!flex [&>span]:!overflow-visible">
            <FilterSelectValue
              label={t("filters.role")}
              value={actorRole === "all" ? tCommon("all") : t(`roles.${actorRole}`)}
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon("all")}</SelectItem>
            {(overview?.roles ?? [])
              .filter((item) => isActorRole(item.key))
              .map((item) => (
                <SelectItem key={item.key} value={item.key}>
                  {t(`roles.${item.key}`)}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
        <Select value={scope} onValueChange={onScope}>
          <SelectTrigger className="h-10 border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-xs [&>span]:!flex [&>span]:!overflow-visible">
            <FilterSelectValue
              label={t("filters.scope")}
              value={scope === "all" ? tCommon("all") : scope}
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon("all")}</SelectItem>
            {(overview?.scopes ?? []).map((item) => (
              <SelectItem key={item.key} value={item.key}>
                {item.key}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={eventType}
          onValueChange={(value) => onEventType(value as AuditEventType | "all")}
        >
          <SelectTrigger className="h-10 border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-xs [&>span]:!flex [&>span]:!overflow-visible">
            <FilterSelectValue
              label={t("filters.eventType")}
              value={eventType === "all" ? tCommon("all") : t(`eventTypes.${eventType}`)}
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon("all")}</SelectItem>
            {EVENT_TYPES.map((item) => (
              <SelectItem key={item} value={item}>
                {t(`eventTypes.${item}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={outcome} onValueChange={(value) => onOutcome(value as AuditOutcome | "all")}>
          <SelectTrigger className="h-10 border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-xs [&>span]:!flex [&>span]:!overflow-visible">
            <FilterSelectValue
              label={t("filters.outcome")}
              value={outcome === "all" ? tCommon("all") : t(`outcomes.${outcome}`)}
            />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{tCommon("all")}</SelectItem>
            {OUTCOMES.map((item) => (
              <SelectItem key={item} value={item}>
                {t(`outcomes.${item}`)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </section>
  );
}

function isActorRole(value: string): value is AuditActorRole {
  return ACTOR_ROLE_SET.has(value);
}

function FilterSelectValue({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex min-w-0 flex-col items-start leading-tight">
      <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{label}</span>
      <span className="max-w-full truncate text-[0.72rem] text-[var(--tessera-text)]">{value}</span>
    </span>
  );
}

function EventTypeTabs({
  overview,
  value,
  onValue,
}: {
  overview: AuditOverview | undefined;
  value: AuditEventType | "all";
  onValue: (value: AuditEventType | "all") => void;
}) {
  const t = useTranslations("audit");
  const countFor = (key: AuditEventType) =>
    overview?.event_types.find((item) => item.key === key)?.count ?? 0;
  return (
    <div className="flex min-h-9 shrink-0 items-center gap-2 overflow-x-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 py-1">
      <TabButton
        active={value === "all"}
        label={t("eventTypes.all")}
        count={overview?.total_events ?? 0}
        onClick={() => onValue("all")}
      />
      {EVENT_TYPES.map((item) => (
        <TabButton
          key={item}
          active={value === item}
          label={t(`eventTypes.${item}`)}
          count={countFor(item)}
          onClick={() => onValue(item)}
        />
      ))}
    </div>
  );
}

function TabButton({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean;
  label: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-7 shrink-0 items-center gap-2 rounded-md border px-3 text-xs transition-colors",
        active
          ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
          : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
      )}
    >
      <span>{label}</span>
      <span className="font-mono text-[0.68rem] text-[var(--tessera-text-muted)]">{count}</span>
    </button>
  );
}

function AuditEventsTable({
  entries,
  selected,
  onSelect,
  formatter,
}: {
  entries: AuditEntry[];
  selected: AuditEntry | null;
  onSelect: (entry: AuditEntry) => void;
  formatter: ReturnType<typeof useFormatter>;
}) {
  const t = useTranslations("audit");
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[132px]">{t("columns.occurredAt")}</TableHead>
          <TableHead>{t("columns.type")}</TableHead>
          <TableHead>{t("columns.object")}</TableHead>
          <TableHead>{t("columns.actor")}</TableHead>
          <TableHead>{t("columns.role")}</TableHead>
          <TableHead>{t("columns.scope")}</TableHead>
          <TableHead>{t("columns.outcome")}</TableHead>
          <TableHead>{t("columns.proof")}</TableHead>
          <TableHead>{t("columns.case")}</TableHead>
          <TableHead className="text-center">{t("columns.decisions")}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {entries.map((entry) => {
          const active = selected ? entryKey(selected) === entryKey(entry) : false;
          return (
            <TableRow
              key={entryKey(entry)}
              className={cn(
                "group cursor-pointer text-xs transition-colors hover:bg-[#0b2b49]",
                active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
              )}
              // biome-ignore lint/a11y/useSemanticElements: a data row opens the adjacent detail panel and remains keyboard reachable
              role="button"
              tabIndex={0}
              aria-label={`${entry.target} ${entry.outcome}`}
              onClick={() => onSelect(entry)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(entry);
                }
              }}
            >
              <TableCell className="font-mono text-[0.68rem] text-[var(--tessera-text-muted)]">
                {formatter.dateTime(new Date(entry.occurred_at), {
                  dateStyle: "short",
                  timeStyle: "medium",
                })}
              </TableCell>
              <TableCell>{t(`eventTypes.${entry.event_type}`)}</TableCell>
              <TableCell className="max-w-[210px] truncate font-medium text-[var(--tessera-text)]">
                {entry.object_label}
              </TableCell>
              <TableCell className="max-w-[160px] truncate">{entry.actor}</TableCell>
              <TableCell>{t(`roles.${entry.actor_role}`)}</TableCell>
              <TableCell className="max-w-[120px] truncate">{entry.scope}</TableCell>
              <TableCell>
                <OutcomeBadge outcome={entry.outcome} />
              </TableCell>
              <TableCell className="font-mono text-[0.68rem] text-[#87bfff]">
                {entry.proof_ref ? (
                  <span className="inline-flex items-center gap-1">
                    {entry.proof_ref}
                    <ExternalLink className="h-3 w-3" />
                  </span>
                ) : (
                  "—"
                )}
              </TableCell>
              <TableCell className="max-w-[170px] truncate">{entry.policy_rule ?? "—"}</TableCell>
              <TableCell className="text-center font-mono">{entry.decisions.length}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function Pagination({
  cursor,
  pageSize,
  hasMore,
  total,
  onPrevious,
  onNext,
}: {
  cursor: number;
  pageSize: number;
  hasMore: boolean;
  total: number | undefined;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const t = useTranslations("common");
  const start = total === 0 ? 0 : cursor + 1;
  const end = Math.min(cursor + pageSize, total ?? cursor + pageSize);
  return (
    <div className="flex min-h-11 items-center justify-between border-t border-[var(--tessera-border)] px-4 py-2 text-xs text-[var(--tessera-text-muted)]">
      <p>
        {start}–{end}
        {typeof total === "number" ? ` / ${total}` : null}
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onPrevious} disabled={cursor === 0}>
          <ChevronLeft className="h-4 w-4" />
          {t("previous")}
        </Button>
        <Button variant="outline" size="sm" onClick={onNext} disabled={!hasMore}>
          {t("next")}
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function BottomPanels({
  overview,
  loading,
}: {
  overview: AuditOverview | undefined;
  loading: boolean;
}) {
  const t = useTranslations("audit.panels");
  return (
    <div className="grid shrink-0 grid-cols-1 gap-3 lg:grid-cols-5">
      <Panel title={t("timeline")}>
        {loading || !overview ? (
          <Skeleton className="h-28 w-full" />
        ) : (
          <TimelineChart overview={overview} />
        )}
      </Panel>
      <Panel title={t("actors")}>
        <CountList items={overview?.actors ?? []} loading={loading} />
      </Panel>
      <Panel title={t("policies")}>
        <CountList items={overview?.policies ?? []} loading={loading} danger />
      </Panel>
      <Panel title={t("proofs")}>
        <ProofList overview={overview} loading={loading} />
      </Panel>
      <Panel title={t("filters")}>
        <CountList items={overview?.suggested_filters ?? []} loading={loading} />
      </Panel>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex h-[142px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h2 className="shrink-0 font-sans text-sm font-semibold text-[var(--tessera-text)]">
        {title}
      </h2>
      <div className="mt-2 min-h-0 flex-1 overflow-hidden pb-1">{children}</div>
    </section>
  );
}

function CountList({
  items,
  loading,
  danger,
}: {
  items: { key: string; count: number }[];
  loading: boolean;
  danger?: boolean;
}) {
  if (loading) return <Skeleton className="h-24 w-full" />;
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <ol className="space-y-1 pb-1">
      {items.slice(0, 3).map((item, index) => (
        <li
          key={`${item.key}-${index}`}
          className="grid grid-cols-[1rem_minmax(0,1fr)_auto] items-center gap-2 text-[0.72rem] leading-tight"
        >
          <span className="font-mono text-[var(--tessera-text-muted)]">{index + 1}</span>
          <div className="min-w-0">
            <p className="truncate text-[var(--tessera-text)]">{item.key}</p>
            <div className="mt-0.5 h-1.5 rounded-full bg-[var(--tessera-bg)]">
              <div
                className={cn("h-full rounded-full", danger ? "bg-red-400" : "bg-[#2e72d2]")}
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
          </div>
          <span className="font-mono text-[var(--tessera-text-muted)]">{item.count}</span>
        </li>
      ))}
    </ol>
  );
}

function TimelineChart({ overview }: { overview: AuditOverview }) {
  const total = overview.timeline.map((bucket) => bucket.total);
  const denied = overview.timeline.map((bucket) => bucket.denied);
  const ticks = timelineTicks(overview.timeline);
  return (
    <div className="flex h-full flex-col justify-end gap-1.5 pb-1">
      <svg
        viewBox="0 0 220 64"
        preserveAspectRatio="none"
        className="h-[58px] w-full shrink-0"
        aria-hidden="true"
      >
        <title>{overview.total_events}</title>
        <line
          x1="0"
          x2="220"
          y1="58"
          y2="58"
          stroke="currentColor"
          vectorEffect="non-scaling-stroke"
          className="text-[var(--tessera-border)]"
        />
        <polyline
          points={polyline(total, 220, 56)}
          fill="none"
          stroke="#2e72d2"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
        <polyline
          points={polyline(denied, 220, 56)}
          fill="none"
          stroke="#ff7a59"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="grid grid-cols-4 gap-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
        {ticks.map((bucket, index) => (
          <span
            key={bucket.start}
            className={cn(
              "min-w-0 truncate",
              index === 0 ? "text-left" : index === ticks.length - 1 ? "text-right" : "text-center",
            )}
          >
            {bucket.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function timelineTicks(timeline: AuditOverview["timeline"]): AuditOverview["timeline"] {
  if (timeline.length <= 4) return timeline;
  const indexes = new Set([
    0,
    Math.floor((timeline.length - 1) / 3),
    Math.floor(((timeline.length - 1) * 2) / 3),
    timeline.length - 1,
  ]);
  return [...indexes]
    .sort((a, b) => a - b)
    .map((index) => timeline[index])
    .filter((bucket): bucket is AuditOverview["timeline"][number] => Boolean(bucket));
}

function ProofList({
  overview,
  loading,
}: {
  overview: AuditOverview | undefined;
  loading: boolean;
}) {
  const formatter = useFormatter();
  if (loading) return <Skeleton className="h-24 w-full" />;
  return (
    <ul className="space-y-1 pb-1">
      {(overview?.recent_proofs ?? []).slice(0, 3).map((proof) => (
        <li key={proof.hash} className="flex items-start gap-1.5 text-[0.7rem] leading-tight">
          <FileJson className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
          <div className="min-w-0">
            <p className="truncate font-mono text-[var(--tessera-text)]">
              {proof.hash.slice(0, 14)}
            </p>
            <p className="truncate text-[0.58rem] leading-tight text-[var(--tessera-text-muted)]">
              {formatter.dateTime(new Date(proof.occurred_at), {
                dateStyle: "short",
                timeStyle: "short",
              })}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function AuditDetailOverlay({
  entry,
  overview,
  onClose,
}: {
  entry: AuditEntry;
  overview: AuditOverview | undefined;
  onClose: () => void;
}) {
  return (
    <div
      className="absolute inset-0 z-30 flex justify-end overflow-hidden rounded-lg bg-[#020817]/70 backdrop-blur-[2px]"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <AuditDetails entry={entry} overview={overview} onClose={onClose} />
    </div>
  );
}

function AuditDetails({
  entry,
  overview,
  onClose,
}: {
  entry: AuditEntry;
  overview: AuditOverview | undefined;
  onClose: () => void;
}) {
  const t = useTranslations("audit");
  const tCommon = useTranslations("common");
  const formatter = useFormatter();
  const firstDecision = entry.decisions[0];
  const rationale = firstDecision?.rationale || entry.policy_rule || entry.error || "—";
  const eventJson = JSON.stringify(entry, null, 2);
  return (
    <dialog
      open
      aria-modal="true"
      aria-label={t("detail.title")}
      className="static m-0 flex h-full w-full max-w-[480px] flex-col overflow-hidden border-0 border-l border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-0 text-[var(--tessera-text)] shadow-[-24px_0_60px_rgba(0,0,0,0.35)]"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="z-10 flex shrink-0 items-center justify-between border-b border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-3">
        <h2 className="font-sans text-base font-semibold">{t("detail.title")}</h2>
        <div className="flex items-center gap-2">
          <OutcomeBadge outcome={entry.outcome} />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={tCommon("close")}
            className="h-7 w-7 text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4">
        <DetailSection>
          <DetailRow
            label={t("detail.eventId")}
            value={entry.proof_ref ?? entry.hash?.slice(0, 12) ?? "—"}
            mono
          />
          <DetailRow
            label={t("detail.timestamp")}
            value={formatter.dateTime(new Date(entry.occurred_at), {
              dateStyle: "medium",
              timeStyle: "medium",
            })}
          />
          <DetailRow
            label={t("detail.actor")}
            value={entry.actor}
            badge={t(`roles.${entry.actor_role}`)}
          />
          <DetailRow label={t("detail.scope")} value={entry.scope} />
          <DetailRow label={t("detail.action")} value={entry.target} />
          <DetailRow label={t("detail.object")} value={entry.object_label} />
          <DetailRow label={t("detail.policy")} value={rationale} />
        </DetailSection>

        <DetailBlock title={t("detail.causality")}>
          <CausalityChain entry={entry} />
        </DetailBlock>

        <DetailBlock title={t("detail.diff")}>
          <DiffPanel entry={entry} />
        </DetailBlock>

        <DetailBlock title={t("detail.proof")}>
          <DetailRow label={t("detail.hash")} value={entry.hash ?? "—"} mono />
          <DetailRow label={t("detail.prevHash")} value={entry.prev_hash ?? "—"} mono />
          <DetailRow
            label={t("detail.chain")}
            value={overview?.chain_verified ? t("integrity.ok") : t("integrity.unknown")}
          />
        </DetailBlock>

        <DetailBlock title={t("payload")}>
          <pre className="max-h-44 overflow-auto rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 font-mono text-[0.68rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {JSON.stringify(entry.arguments, null, 2)}
          </pre>
        </DetailBlock>

        <DetailBlock title={t("detail.links")}>
          <DetailRow label={t("columns.type")} value={t(`eventTypes.${entry.event_type}`)} />
          <DetailRow label={t("columns.case")} value={entry.policy_rule ?? "—"} />
          <DetailRow label={t("detail.model")} value={entry.model ?? "—"} />
        </DetailBlock>
      </div>
      <QuickActions entry={entry} eventJson={eventJson} />
    </dialog>
  );
}

function QuickActions({ entry, eventJson }: { entry: AuditEntry; eventJson: string }) {
  const t = useTranslations("audit");
  return (
    <div className="shrink-0 border-t border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="font-sans text-sm font-semibold">{t("actions.title")}</h3>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <ActionButton
          icon="copy"
          label={t("actions.copyId")}
          value={entry.proof_ref ?? entry.hash ?? ""}
        />
        <ActionButton
          icon="proof"
          label={t("actions.openProof")}
          value={eventJson}
          downloadName="tessera-audit-event.json"
        />
        <ActionButton
          icon="policy"
          label={t("actions.viewPolicy")}
          value={entry.policy_rule ?? ""}
        />
        <ActionButton icon="case" label={t("actions.openCase")} value={entry.object_label} />
      </div>
    </div>
  );
}

function CausalityChain({ entry }: { entry: AuditEntry }) {
  const t = useTranslations("audit");
  const steps = [
    { key: "request", label: t("detail.steps.request"), sub: entry.actor },
    { key: "policy", label: t("detail.steps.policy"), sub: entry.policy_rule ?? "—" },
    { key: "decision", label: t("detail.steps.decision"), sub: t(`outcomes.${entry.outcome}`) },
    { key: "proof", label: t("detail.steps.proof"), sub: entry.proof_ref ?? "—" },
  ];
  return (
    <div className="relative px-2 pb-1 pt-2">
      <div className="absolute left-[10%] right-[10%] top-[21px] h-px bg-[#1b805f]" />
      <div className="relative grid grid-cols-4 gap-2">
        {steps.map((step, index) => (
          <div key={step.key} className="min-w-0 text-center">
            <div className="mx-auto flex h-7 w-7 items-center justify-center rounded-full border border-[#1b805f] bg-[#05281f] text-[0.7rem] font-semibold text-[var(--tessera-green)] shadow-[0_0_0_4px_var(--tessera-surface)]">
              {index + 1}
            </div>
            <p className="mt-1 truncate text-[0.65rem] text-[var(--tessera-text)]">{step.label}</p>
            <p className="truncate text-[0.58rem] text-[var(--tessera-text-muted)]">{step.sub}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function DiffPanel({ entry }: { entry: AuditEntry }) {
  const t = useTranslations("audit.detail");
  const firstDecision = entry.decisions[0];
  const after = {
    outcome: entry.outcome,
    policy_rule: entry.policy_rule,
    decision: firstDecision?.decision ?? null,
    redactions: firstDecision?.redactions ?? [],
  };
  return (
    <div className="grid gap-2">
      <DiffColumn title={t("before")} payload={entry.arguments} />
      <DiffColumn title={t("after")} payload={after} after />
    </div>
  );
}

function DiffColumn({
  title,
  payload,
  after,
}: {
  title: string;
  payload: unknown;
  after?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-md border border-[var(--tessera-border)] p-3">
      <p className="mb-2 text-[0.65rem] font-medium text-[var(--tessera-text-muted)]">{title}</p>
      <pre
        className={cn(
          "max-h-32 overflow-auto whitespace-pre rounded bg-[var(--tessera-bg)] p-2 font-mono text-[0.62rem] leading-relaxed",
          after ? "text-[var(--tessera-green)]" : "text-[var(--tessera-text-muted)]",
        )}
      >
        {JSON.stringify(payload, null, 2)}
      </pre>
    </div>
  );
}

function DetailSection({ children }: { children: React.ReactNode }) {
  return <section className="space-y-2">{children}</section>;
}

function DetailBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-[var(--tessera-border)] pt-4">
      <h3 className="font-sans text-sm font-semibold">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function DetailRow({
  label,
  value,
  badge,
  mono,
}: {
  label: string;
  value: string;
  badge?: string;
  mono?: boolean;
}) {
  return (
    <div className="grid grid-cols-[116px_minmax(0,1fr)] gap-3 text-xs">
      <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
      <dd
        className={cn(
          "min-w-0 truncate text-[var(--tessera-text)]",
          mono && "font-mono text-[0.68rem]",
        )}
      >
        {value}
        {badge ? (
          <span className="ml-2 rounded bg-[var(--tessera-muted)] px-1.5 py-0.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
            {badge}
          </span>
        ) : null}
      </dd>
    </div>
  );
}

function ActionButton({
  icon,
  label,
  value,
  downloadName,
}: {
  icon: "copy" | "proof" | "policy" | "case";
  label: string;
  value: string;
  downloadName?: string;
}) {
  const Icon =
    icon === "copy"
      ? Copy
      : icon === "proof"
        ? FileJson
        : icon === "policy"
          ? ShieldCheck
          : ExternalLink;
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-7 justify-start gap-1.5 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 text-[0.68rem]"
      onClick={() => {
        if (downloadName) {
          const blob = new Blob([value], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = downloadName;
          a.click();
          URL.revokeObjectURL(url);
          return;
        }
        void navigator.clipboard?.writeText(value);
      }}
    >
      <Icon className="h-3.5 w-3.5" />
      {label}
    </Button>
  );
}

function AuditFooter({
  overview,
  formatter,
}: {
  overview: AuditOverview | undefined;
  formatter: ReturnType<typeof useFormatter>;
}) {
  const t = useTranslations("audit.footer");
  return (
    <footer className="grid min-h-[48px] shrink-0 grid-cols-1 gap-3 border-t border-[var(--tessera-border)] pt-2 text-xs text-[var(--tessera-text-muted)] md:grid-cols-5">
      <FooterItem
        icon={<ShieldCheck />}
        label={t("integrity")}
        value={overview?.chain_verified ? t("conform") : t("unknown")}
      />
      <FooterItem icon={<Database />} label={t("source")} value={t("ledger")} />
      <FooterItem
        icon={<FileJson />}
        label={t("proofs")}
        value={String(overview?.chain_length ?? "—")}
      />
      <FooterItem
        icon={<Hash />}
        label={t("lastCheck")}
        value={
          overview
            ? formatter.dateTime(new Date(overview.generated_at), {
                dateStyle: "short",
                timeStyle: "medium",
              })
            : "—"
        }
      />
      <FooterItem
        icon={<KeyRound />}
        label={t("clock")}
        value={
          overview
            ? formatter.dateTime(new Date(overview.window_end), { timeStyle: "medium" })
            : "—"
        }
      />
    </footer>
  );
}

function FooterItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[var(--tessera-green)] [&_svg]:h-5 [&_svg]:w-5">{icon}</span>
      <div className="min-w-0">
        <p className="truncate font-medium text-[var(--tessera-text)]">{label}</p>
        <p className="truncate">{value}</p>
      </div>
    </div>
  );
}

function OutcomeBadge({ outcome }: { outcome: AuditOutcome }) {
  const t = useTranslations("audit.outcomes");
  if (outcome === "allowed")
    return (
      <Badge tone="success" className="gap-1">
        <ShieldCheck className="h-3 w-3" /> {t("allowed")}
      </Badge>
    );
  if (outcome === "denied")
    return (
      <Badge tone="danger" className="gap-1">
        <ShieldOff className="h-3 w-3" /> {t("denied")}
      </Badge>
    );
  return (
    <Badge tone="warning" className="gap-1">
      <ShieldAlert className="h-3 w-3" /> {t("error")}
    </Badge>
  );
}

function entryKey(entry: AuditEntry): string {
  return `${entry.occurred_at}-${entry.target}-${entry.hash ?? entry.proof_ref ?? entry.object_label}`;
}

function polyline(values: number[], width: number, height: number): string {
  if (values.length === 0) return "";
  const max = Math.max(...values, 1);
  const last = Math.max(values.length - 1, 1);
  return values
    .map((value, index) => {
      const x = (index / last) * width;
      const y = height - (value / max) * (height - 8);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

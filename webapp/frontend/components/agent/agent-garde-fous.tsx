"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FlaskConical,
  type LucideIcon,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CardInfo } from "@/components/cockpit/card-info";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchAgentGardeFous, mutateGardeFousRule } from "@/lib/api/client";
import type { AgentGardeFous as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

import { AgentCrossLinks } from "./agent-cross-links";

type RowT = NonNullable<Data["table"]>["rows"][number];
type DetailT = NonNullable<Data["details"]>[number];

const KPI_ICONS: LucideIcon[] = [
  ShieldCheck,
  SlidersHorizontal,
  ShieldAlert,
  AlertTriangle,
  ShieldAlert,
  FlaskConical,
];
const SEV_TONE: Record<string, string> = {
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
  high: "border-orange-500/30 bg-orange-500/15 text-orange-300",
  mod: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  maj: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  low: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const MODE_DOT: Record<string, string> = {
  block: "bg-red-400",
  limit: "bg-amber-400",
  warn: "bg-sky-400",
  allow: "bg-emerald-400",
  confirm: "bg-violet-400",
};
const COV_BAR: Record<string, string> = {
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
};
const WATCH_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  crit: "bg-red-400",
};
const FIELD_DOT: Record<string, string> = {
  crit: "text-red-400",
  high: "text-[var(--tessera-fg-warning)]",
  mod: "text-[var(--tessera-fg-warning)]",
  low: "text-[var(--tessera-fg-info)]",
  good: "text-emerald-400",
};

const ALL = "all" as const;

/** Close a popover on outside-click and Escape; attach the returned ref to its root. */
function useDismiss(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);
  return ref;
}

export function AgentGardeFous() {
  const t = useTranslations("agentGardeFous");
  const locale = useLocale();
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["agent-garde-fous", locale],
    queryFn: ({ signal }) => fetchAgentGardeFous(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [mutError, setMutError] = useState(false);
  const mutate = useMutation({
    mutationFn: mutateGardeFousRule,
    onSuccess: (fresh) => {
      setMutError(false);
      qc.setQueryData(["agent-garde-fous", locale], fresh);
    },
    onError: () => setMutError(true),
  });

  const [search, setSearch] = useState("");
  const [cat, setCat] = useState<string>(ALL);
  const [status, setStatus] = useState<string>(ALL);
  const [sev, setSev] = useState<string>(ALL);
  const [mode, setMode] = useState<string>(ALL);
  const [selected, setSelected] = useState<string | null>(null);

  const rows = data?.table?.rows ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (q === "" || r.name.toLowerCase().includes(q)) &&
        (cat === ALL || r.category_key === cat) &&
        (status === ALL || r.status_tone === status) &&
        (sev === ALL || r.sev_tone === sev) &&
        (mode === ALL || r.mode_tone === mode),
    );
  }, [rows, search, cat, status, sev, mode]);

  const details = data?.details ?? [];
  const detail = details.find((d) => d.key === selected) ?? details[0] ?? null;

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  const a = data.actions;
  const anyFilter = search !== "" || cat !== ALL || status !== ALL || sev !== ALL || mode !== ALL;
  const resetAll = () => {
    setSearch("");
    setCat(ALL);
    setStatus(ALL);
    setSev(ALL);
    setMode(ALL);
  };

  return (
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="garde-fous" />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => temporal.changeMode("history")}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <CalendarClock className="h-4 w-4" /> {a?.asof}
        </button>
        <Link
          href={"/configurer/garde-fous" as Route}
          className="flex h-9 items-center gap-2 rounded-md border border-[#d98b1f] bg-[#e0a23a] px-3 text-xs font-medium text-[#1b1402] hover:bg-[#eab44e]"
        >
          <Plus className="h-4 w-4" /> {a?.create}
        </Link>
      </div>

      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        windowEnd={temporal.windowEnd}
        onPickDate={temporal.pickDate}
        onModeChange={temporal.changeMode}
      />

      {mutError ? (
        <div className="rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-[0.72rem] text-red-300">
          {t("mutationError")}
        </div>
      ) : null}

      <Snapshot data={data} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? ShieldCheck} />
        ))}
      </div>

      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
          <Filters
            data={data}
            search={search}
            setSearch={setSearch}
            cat={cat}
            setCat={setCat}
            status={status}
            setStatus={setStatus}
            sev={sev}
            setSev={setSev}
            mode={mode}
            setMode={setMode}
            rows={rows}
            anyFilter={anyFilter}
            onReset={resetAll}
          />
          {anyFilter ? (
            <div className="flex flex-wrap items-center gap-1.5" aria-live="polite">
              {search !== "" ? (
                <Chip label={`${t("searchPrefix")}: ${search}`} onRemove={() => setSearch("")} />
              ) : null}
              {cat !== ALL ? (
                <Chip
                  label={labelFor(rows, "category_key", "category", cat)}
                  onRemove={() => setCat(ALL)}
                />
              ) : null}
              {status !== ALL ? (
                <Chip
                  label={labelFor(rows, "status_tone", "status", status)}
                  onRemove={() => setStatus(ALL)}
                />
              ) : null}
              {sev !== ALL ? (
                <Chip
                  label={labelFor(rows, "sev_tone", "severity", sev)}
                  onRemove={() => setSev(ALL)}
                />
              ) : null}
              {mode !== ALL ? (
                <Chip
                  label={labelFor(rows, "mode_tone", "mode", mode)}
                  onRemove={() => setMode(ALL)}
                />
              ) : null}
              <button
                type="button"
                onClick={resetAll}
                className="text-[0.66rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
              >
                {t("clearAll")}
              </button>
            </div>
          ) : null}
          <RulesTable
            data={data}
            rows={filtered}
            total={rows.length}
            selected={detail?.key ?? null}
            onSelect={setSelected}
          />
          <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-4">
            <Watch data={data} />
            <Quick data={data} />
            <Coverage data={data} />
            <Reasons data={data} />
          </div>
          <div className="grid gap-2.5 md:grid-cols-2">
            <ModeDistribution data={data} />
            <Overrides data={data} />
          </div>
        </div>
        <Detail
          detail={detail}
          className="xl:col-span-4"
          busy={mutate.isPending}
          onToggle={(key, enabled) => mutate.mutate({ key, enabled, lang: locale })}
        />
      </div>
    </div>
  );
}

function labelFor(
  rows: RowT[],
  keyField: keyof RowT,
  labelField: keyof RowT,
  value: string,
): string {
  const hit = rows.find((r) => String(r[keyField]) === value);
  return hit ? String(hit[labelField]) : value;
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 text-[0.64rem] text-[var(--tessera-text)]">
      <Truncate full={label} className="max-w-[200px]">
        {label}
      </Truncate>
      <button type="button" onClick={onRemove} aria-label={`Remove ${label}`}>
        <X className="h-3 w-3 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]" />
      </button>
    </span>
  );
}

function Snapshot({ data }: { data: Data }) {
  const s = data.snapshot;
  if (!s) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-x-7 gap-y-2">
        <Field>
          <span className="flex items-center gap-1.5 text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <Clock className="h-3.5 w-3.5 text-[var(--tessera-fg-info)]" /> {s.tag}
          </span>
          <span className="flex items-center gap-1 text-[0.92rem] font-semibold text-[var(--tessera-text)]">
            {s.label}
            <CardInfo ns="agentGardeFous" k="snapshot" title={s.label} />
          </span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.updated_label}</span>
          <span className="text-[0.82rem] font-medium tabular-nums text-[var(--tessera-text)]">
            {s.updated}
          </span>
          <span className="text-[0.58rem] text-[var(--tessera-text-muted)]">{s.updated_rel}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.version_label}</span>
          <span className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{s.version}</span>
          <span className="text-[0.58rem] text-[var(--tessera-fg-success)]">
            {s.version_status}
          </span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.evalset_label}</span>
          <span className="text-[0.82rem] font-medium tabular-nums text-[var(--tessera-text)]">
            {s.evalset}
          </span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.coverage_label}</span>
          <span className="flex items-center gap-2">
            <Gauge pct={s.coverage} />
            <span className="text-[0.7rem] text-[var(--tessera-fg-success)]">
              {s.coverage_tone}
            </span>
          </span>
        </Field>
      </div>
      {/* No as-of / compare controls here: this snapshot is the CURRENT policy
          only. The two buttons that used to sit here had no onClick — a control
          that promises an as-of the page cannot serve is a lie (registre §1);
          per-object history is OT-01, still to build. */}
    </div>
  );
}

function Field({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-0.5">{children}</div>;
}

function Gauge({ pct }: { pct: number }) {
  const r = 11;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <span className="relative inline-flex h-8 w-8 items-center justify-center">
      <svg viewBox="0 0 28 28" className="h-8 w-8 -rotate-90" aria-hidden="true">
        <circle cx="14" cy="14" r={r} fill="none" stroke="var(--tessera-border)" strokeWidth="3" />
        <circle
          cx="14"
          cy="14"
          r={r}
          fill="none"
          stroke="#34d399"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={off}
        />
      </svg>
      <span className="absolute text-[0.52rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {pct}%
      </span>
    </span>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[88px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <Truncate full={kpi.label} className="text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </Truncate>
        <CardInfo ns="agentGardeFous" k={kpi.key} title={kpi.label} />
      </div>
      <div>
        <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text)]">
          {kpi.value}
        </p>
        <p
          className={cn(
            "truncate text-[0.6rem] tabular-nums",
            kpi.good ? "text-emerald-400" : "text-red-400",
          )}
        >
          {kpi.delta}
        </p>
      </div>
    </div>
  );
}

function FilterDropdown({
  label,
  value,
  options,
  onSelect,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onSelect: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  const current = options.find((o) => o.value === value)?.label ?? value;
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] hover:border-[var(--tessera-text-muted)]"
      >
        <span className="text-[var(--tessera-text-muted)]">{label}</span>
        <span className="font-medium text-[var(--tessera-text)]">{current}</span>
        <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute left-0 z-20 mt-1 w-52 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="menuitem"
              onClick={() => {
                onSelect(o.value);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[0.72rem] hover:bg-[var(--tessera-bg)]",
                o.value === value
                  ? "text-[var(--tessera-text)]"
                  : "text-[var(--tessera-text-muted)]",
              )}
            >
              {o.label}
              {o.value === value ? (
                <span className="text-[var(--tessera-fg-teal)]">&bull;</span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function uniqueOptions(
  rows: RowT[],
  keyField: keyof RowT,
  labelField: keyof RowT,
  allLabel: string,
) {
  const seen = new Map<string, string>();
  for (const r of rows) seen.set(String(r[keyField]), String(r[labelField]));
  return [
    { value: ALL, label: allLabel },
    ...[...seen.entries()].map(([value, label]) => ({ value, label })),
  ];
}

function Filters({
  data,
  search,
  setSearch,
  cat,
  setCat,
  status,
  setStatus,
  sev,
  setSev,
  mode,
  setMode,
  rows,
  anyFilter,
  onReset,
}: {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  cat: string;
  setCat: (v: string) => void;
  status: string;
  setStatus: (v: string) => void;
  sev: string;
  setSev: (v: string) => void;
  mode: string;
  setMode: (v: string) => void;
  rows: RowT[];
  anyFilter: boolean;
  onReset: () => void;
}) {
  const t = useTranslations("agentGardeFous");
  const f = data.filters;
  const [advOpen, setAdvOpen] = useState(false);
  const advRef = useDismiss(
    advOpen,
    useCallback(() => setAdvOpen(false), []),
  );
  if (!f) return null;
  const [allF, allM] = [f.selects[0]?.value ?? "Toutes", f.selects[1]?.value ?? "Tous"];
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[200px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={f.search}
          aria-label={f.search}
          className="w-full bg-transparent text-[0.74rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
        />
      </div>
      <FilterDropdown
        label={f.selects[0]?.label ?? t("filterCategory")}
        value={cat}
        options={uniqueOptions(rows, "category_key", "category", allF)}
        onSelect={setCat}
      />
      <FilterDropdown
        label={f.selects[1]?.label ?? t("filterStatus")}
        value={status}
        options={uniqueOptions(rows, "status_tone", "status", allM)}
        onSelect={setStatus}
      />
      <FilterDropdown
        label={f.selects[2]?.label ?? t("filterSeverity")}
        value={sev}
        options={uniqueOptions(rows, "sev_tone", "severity", allF)}
        onSelect={setSev}
      />
      <div className="relative" ref={advRef}>
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={advOpen}
          onClick={() => setAdvOpen((o) => !o)}
          className={cn(
            "flex h-9 items-center gap-1.5 rounded-md border bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] hover:border-[var(--tessera-text-muted)]",
            mode !== ALL
              ? "border-[#7c5cf5]/60 text-[var(--tessera-text)]"
              : "border-[var(--tessera-border)] text-[var(--tessera-text-muted)]",
          )}
        >
          <SlidersHorizontal className="h-3.5 w-3.5" /> {f.more}
          {mode !== ALL ? (
            <span className="ml-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[#6d4aed] px-1 text-[0.56rem] font-semibold text-white">
              1
            </span>
          ) : null}
        </button>
        {advOpen ? (
          <div
            role="menu"
            className="absolute right-0 z-20 mt-1 w-56 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2 shadow-lg"
          >
            <p className="mb-1.5 px-1 text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {t("filterMode")}
            </p>
            <div className="flex flex-col gap-0.5">
              {uniqueOptions(rows, "mode_tone", "mode", allM).map((o) => (
                <button
                  key={o.value}
                  type="button"
                  role="menuitem"
                  onClick={() => setMode(o.value)}
                  className={cn(
                    "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[0.72rem] hover:bg-[var(--tessera-bg)]",
                    o.value === mode
                      ? "text-[var(--tessera-text)]"
                      : "text-[var(--tessera-text-muted)]",
                  )}
                >
                  {o.label}
                  {o.value === mode ? (
                    <span className="text-[var(--tessera-fg-teal)]">&bull;</span>
                  ) : null}
                </button>
              ))}
            </div>
            {anyFilter ? (
              <button
                type="button"
                onClick={() => {
                  onReset();
                  setAdvOpen(false);
                }}
                className="mt-1.5 w-full rounded border border-[var(--tessera-border)] px-2 py-1.5 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
              >
                {t("reset")}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RulesTable({
  data,
  rows,
  total,
  selected,
  onSelect,
}: {
  data: Data;
  rows: RowT[];
  total: number;
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const t = useTranslations("agentGardeFous");
  const tbl = data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => (
                <th
                  key={c}
                  className={cn("px-3 py-2 font-medium", i === 0 ? "" : "whitespace-nowrap")}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length}
                  className="px-3 py-10 text-center text-[0.74rem] text-[var(--tessera-text-muted)]"
                >
                  {t("noResults")}
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const on = r.key === selected;
                return (
                  <tr
                    key={r.key}
                    // biome-ignore lint/a11y/useSemanticElements: a data row selects the rule and stays keyboard reachable
                    role="button"
                    tabIndex={0}
                    aria-label={r.name}
                    aria-pressed={on}
                    onClick={() => onSelect(r.key)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelect(r.key);
                      }
                    }}
                    className={cn(
                      "cursor-pointer border-b border-[var(--tessera-border)]/60 last:border-0 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#7c5cf5]",
                      on ? "bg-[#6d4aed]/10" : "hover:bg-[var(--tessera-bg)]/40",
                    )}
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 shrink-0 text-[var(--tessera-fg-info)]" />
                        <Truncate
                          full={r.name}
                          className="text-[0.74rem] font-medium text-[var(--tessera-text)]"
                        >
                          {r.name}
                        </Truncate>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
                      {r.category}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                          SEV_TONE[r.sev_tone] ?? SEV_TONE.mod,
                        )}
                      >
                        {r.severity}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 text-[0.68rem]",
                          r.status_tone === "good"
                            ? "text-[var(--tessera-fg-success)]"
                            : "text-[var(--tessera-fg-danger)]",
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            r.status_tone === "good" ? "bg-emerald-400" : "bg-red-400",
                          )}
                        />
                        {r.status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-[var(--tessera-text)]">
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            MODE_DOT[r.mode_tone] ?? "bg-slate-400",
                          )}
                        />
                        {r.mode}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="w-9 shrink-0 text-[0.7rem] tabular-nums text-[var(--tessera-text)]">
                          {r.coverage}%
                        </span>
                        <span className="hidden h-[4px] w-14 overflow-hidden rounded-full bg-[var(--tessera-border)] lg:block">
                          <span
                            className={cn(
                              "block h-full rounded-full",
                              r.coverage >= 90
                                ? COV_BAR.green
                                : r.coverage >= 50
                                  ? COV_BAR.amber
                                  : COV_BAR.red,
                            )}
                            style={{ width: `${Math.max(r.coverage, 2)}%` }}
                          />
                        </span>
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <span className="block text-[0.7rem] text-[var(--tessera-text)]">
                        {r.updated}
                      </span>
                      <span className="block text-[0.6rem] text-[var(--tessera-text-muted)]">
                        {r.author}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 text-[0.68rem]",
                          r.test_tone === "good"
                            ? "text-[var(--tessera-fg-success)]"
                            : "text-[var(--tessera-text-muted)]",
                        )}
                      >
                        {r.test_tone === "good" ? <CheckCircle2 className="h-3.5 w-3.5" /> : null}
                        {r.test_status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        <span>{t("ruleCount", { shown: rows.length, total })}</span>
      </div>
    </section>
  );
}

function PanelCard({
  title,
  infoK,
  children,
}: {
  title: string;
  infoK?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1 text-[0.74rem] font-semibold text-[var(--tessera-text)]">
          {title}
          {infoK ? <CardInfo ns="agentGardeFous" k={infoK} title={title} /> : null}
        </h3>
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </section>
  );
}

function Watch({ data }: { data: Data }) {
  const w = data.watch;
  if (!w) return null;
  return (
    <PanelCard title={w.title} infoK="watch">
      <ul className="flex flex-col gap-2.5">
        {w.items.map((it) => (
          <li key={it.title} className="flex items-start gap-2">
            <span
              className={cn(
                "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                WATCH_DOT[it.tone] ?? "bg-slate-400",
              )}
            />
            <span className="min-w-0">
              <span className="block text-[0.72rem] leading-snug text-[var(--tessera-text)]">
                {it.title}
              </span>
              {it.detail ? (
                <Truncate
                  full={it.detail}
                  className="text-[0.62rem] text-[var(--tessera-text-muted)]"
                >
                  {it.detail}
                </Truncate>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
      <Link
        href={"/prouver/audit-logs" as Route}
        className="mt-2.5 flex items-center gap-1 self-start text-[0.66rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
      >
        {w.cta} <ChevronRight className="h-3.5 w-3.5" />
      </Link>
    </PanelCard>
  );
}

function Quick({ data }: { data: Data }) {
  const q = data.quick;
  if (!q) return null;
  return (
    <PanelCard title={q.title} infoK="quick">
      <div className="flex flex-col gap-2">
        {q.items.map((it) => (
          <Link
            key={it.href}
            href={it.href as Route}
            className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.72rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
          >
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-accent)]" />
            <Truncate full={it.label} className="min-w-0">
              {it.label}
            </Truncate>
          </Link>
        ))}
      </div>
    </PanelCard>
  );
}

function Coverage({ data }: { data: Data }) {
  const c = data.coverage;
  if (!c) return null;
  return (
    <PanelCard title={c.title} infoK="coverage">
      <ul className="flex flex-col gap-2.5">
        {c.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.7rem]">
              <span className="text-[var(--tessera-text)]">{it.label}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.pct}%</span>
            </div>
            <div className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
              <div
                className={cn("h-full rounded-full", COV_BAR[it.tone] ?? "bg-slate-500")}
                style={{ width: `${it.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function Reasons({ data }: { data: Data }) {
  const r = data.reasons;
  if (!r) return null;
  return (
    <PanelCard title={r.title} infoK="reasons">
      {r.items.length === 0 ? (
        <p className="py-2 text-[0.72rem] text-[var(--tessera-text-muted)]">Aucun blocage.</p>
      ) : null}
      <ul className="flex flex-col gap-2.5">
        {r.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.7rem]">
              <span className="text-[var(--tessera-text)]">{it.label}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.count}</span>
            </div>
            <div className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
              <div
                className={cn("h-full rounded-full", COV_BAR[it.tone] ?? "bg-slate-500")}
                style={{ width: `${it.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

/** Enforcement-mode distribution, derived from the real policy mechanisms. */
function ModeDistribution({ data }: { data: Data }) {
  const m = data.mode_distribution;
  if (!m) return null;
  return (
    <PanelCard title={m.title} infoK="mode_distribution">
      <p className="-mt-1 mb-1 text-[0.66rem] text-[var(--tessera-text-muted)]">{m.subtitle}</p>
      <ul className="flex flex-col gap-2.5">
        {m.items.map((it) => (
          <li key={it.mode} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.7rem]">
              <span className="flex items-center gap-1.5 text-[var(--tessera-text)]">
                <span className={cn("h-2 w-2 rounded-full", MODE_DOT[it.mode] ?? "bg-slate-400")} />
                {it.label}
                <span className="text-[var(--tessera-text-muted)]">
                  · {it.active}/{it.count} actives
                </span>
              </span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">
                {it.decisions.toLocaleString("fr-FR")} déc.
              </span>
            </div>
            <div className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
              <div
                className={cn("h-full rounded-full", MODE_DOT[it.mode] ?? "bg-slate-500")}
                style={{ width: `${Math.max(it.pct, 3)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

/** Manual overrides = rules disabled in the durable state store (real source). */
function Overrides({ data }: { data: Data }) {
  const o = data.overrides;
  if (!o) return null;
  return (
    <PanelCard title={o.title} infoK="overrides">
      <p className="-mt-1 mb-1 text-[0.66rem] text-[var(--tessera-text-muted)]">{o.subtitle}</p>
      {o.items.length === 0 ? (
        <p className="py-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{o.empty}</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {o.items.map((it) => (
            <li
              key={it.key}
              className="flex items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5"
            >
              <span className="flex min-w-0 flex-col">
                <Truncate full={it.name} className="text-[0.72rem] text-[var(--tessera-text)]">
                  {it.name}
                </Truncate>
                <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {it.category} · {it.mode}
                </span>
              </span>
              <span className="shrink-0 rounded border border-amber-500/40 bg-amber-500/15 px-1.5 py-0.5 text-[0.62rem] font-medium text-amber-200">
                {it.status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </PanelCard>
  );
}

function Detail({
  detail,
  className,
  busy,
  onToggle,
}: {
  detail: DetailT | null;
  className?: string;
  busy: boolean;
  onToggle: (key: string, enabled: boolean) => void;
}) {
  const t = useTranslations("agentGardeFous");
  const [tab, setTab] = useState(0);
  // Reset to the first tab whenever the selected rule changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on key change
  useEffect(() => setTab(0), [detail?.key]);
  if (!detail) return null;
  const d = detail;
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-3">
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {t("detailEyebrow")}
        </p>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <ShieldCheck className="h-4 w-4 shrink-0 text-[var(--tessera-fg-info)]" />
            <span className="min-w-0">
              <Truncate
                full={d.name}
                className="text-[0.85rem] font-semibold text-[var(--tessera-text)]"
              >
                {d.name}
              </Truncate>
              <Truncate
                full={d.id}
                className="font-mono text-[0.58rem] text-[var(--tessera-text-muted)]"
              >
                {d.id}
              </Truncate>
            </span>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
              d.status_tone === "good"
                ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                : "border-red-500/30 bg-red-500/15 text-red-300",
            )}
          >
            {d.status}
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {d.tabs.map((tb, i) => {
          const on = i === tab;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(i)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
                on
                  ? "border-[#8b7cf0] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tb}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col gap-4 p-3.5">
        {tab === 0 ? (
          <>
            <div>
              <h3 className="mb-1 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                {t("descriptionLabel")}
              </h3>
              <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {d.description}
              </p>
            </div>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {d.fields.map((f) => (
                <li key={f.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
                  <span className="inline-flex items-center gap-1.5 font-medium text-[var(--tessera-text)]">
                    {f.tone ? (
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          f.tone === "good"
                            ? "bg-emerald-400"
                            : f.tone === "crit"
                              ? "bg-red-400"
                              : "bg-amber-400",
                        )}
                      />
                    ) : null}
                    <span className={cn("tabular-nums", f.tone ? FIELD_DOT[f.tone] : "")}>
                      {f.value}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {tab === 1 ? (
          <DetailBlock
            title={d.config_title}
            cta={d.config_cta}
            href={"/configurer/garde-fous" as Route}
          >
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {d.config.map((c) => (
                <li key={c.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{c.label}</span>
                  <Truncate
                    full={c.value}
                    className="min-w-0 font-medium text-[var(--tessera-text)]"
                  >
                    {c.value}
                  </Truncate>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[0.6rem] text-[var(--tessera-text-muted)]">
              {t("policyUpdated", { date: d.policy_updated })}
            </p>
          </DetailBlock>
        ) : null}

        {tab === 2 ? (
          <DetailBlock title={d.rbac_title} cta={d.rbac_cta} href={"/prouver/audit-logs" as Route}>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {d.rbac.map((r) => (
                <li key={r.role} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{r.role}</span>
                  <span className="font-medium tabular-nums text-[var(--tessera-text)]">
                    {r.access}
                  </span>
                </li>
              ))}
            </ul>
          </DetailBlock>
        ) : null}

        <div className="flex items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2">
          <span className="text-[0.72rem] text-[var(--tessera-text)]">{d.toggle_label}</span>
          <button
            type="button"
            role="switch"
            aria-checked={d.enabled}
            aria-label={d.toggle_label}
            disabled={busy}
            onClick={() => onToggle(d.key, !d.enabled)}
            className={cn(
              "relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50",
              d.enabled ? "bg-emerald-500/70" : "bg-[var(--tessera-border)]",
            )}
          >
            <span
              className={cn(
                "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                d.enabled ? "translate-x-4" : "translate-x-0.5",
              )}
            />
          </button>
        </div>
      </div>
    </section>
  );
}

function DetailBlock({
  title,
  cta,
  href,
  children,
}: {
  title: string;
  cta: string;
  href: Route;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
        <Link
          href={href}
          className="text-[0.64rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
        >
          {cta}
        </Link>
      </div>
      {children}
    </div>
  );
}

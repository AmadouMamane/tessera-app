"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Download,
  Search,
  SortAsc,
  SortDesc,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { fetchSignalCatalogue } from "@/lib/api/client";
import type { ScSignal, SignalCatalogue as SignalData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const SEV_BADGE: Record<string, string> = {
  critical: "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
  high: "border-amber-500/30 bg-amber-500/15 text-[var(--tessera-fg-warning)]",
  medium: "border-yellow-500/30 bg-yellow-500/15 text-[var(--tessera-fg-warning)]",
  low: "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]",
};
const STATUS_BADGE: Record<string, string> = {
  active: "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]",
  evaluation: "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]",
  deprecated: "border-amber-500/30 bg-amber-500/15 text-[var(--tessera-fg-warning)]",
  disabled:
    "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
};
const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const STATUS_RANK: Record<string, number> = {
  active: 0,
  evaluation: 1,
  deprecated: 2,
  disabled: 3,
};

type T = ReturnType<typeof useTranslations<"signalCatalogue">>;
type TT = ReturnType<typeof useTranslations<"table">>;
type Data = SignalData;
type SortKey = "name" | "category" | "source" | "severity" | "status" | "quality" | "owner";

function translated(t: T, group: string, value: string): string {
  const key = `${group}.${value}`;
  return t.has(key) ? t(key) : value;
}

const COLS: { key: string; sort?: SortKey; w: string }[] = [
  { key: "name", sort: "name", w: "18%" },
  { key: "category", sort: "category", w: "10%" },
  { key: "source", sort: "source", w: "9%" },
  { key: "severity", sort: "severity", w: "10%" },
  { key: "status", sort: "status", w: "11%" },
  { key: "quality", sort: "quality", w: "10%" },
  { key: "lastActivity", w: "10%" },
  { key: "owner", sort: "owner", w: "12%" },
  { key: "modified", w: "10%" },
];
const ROWS_PER_PAGE_OPTS = [10, 25, 50];
const ACCENT = "var(--tessera-fg-info)";

export function SignalCatalogue() {
  const t = useTranslations("signalCatalogue");
  const tt = useTranslations("table");
  const locale = useLocale();
  const { data } = useQuery({
    queryKey: ["signal-catalogue", locale],
    queryFn: ({ signal }) => fetchSignalCatalogue(locale, signal),
    staleTime: 60_000,
  });

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [category, setCategory] = useState("all");
  const [source, setSource] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "severity", dir: 1 });
  const [selected, setSelected] = useState<ScSignal | null>(null);

  const signals = useMemo(() => data?.signals ?? [], [data]);
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = signals.filter((s) => {
      if (status !== "all" && s.status !== status) return false;
      if (severity !== "all" && s.severity !== severity) return false;
      if (category !== "all" && s.category !== category) return false;
      if (source !== "all" && s.source !== source) return false;
      if (!q) return true;
      return `${s.name} ${translated(t, "name", s.name)} ${s.description} ${s.id} ${s.owner}`
        .toLowerCase()
        .includes(q);
    });
    const dir = sort.dir;
    return [...filtered].sort((a, b) => {
      switch (sort.key) {
        case "quality":
          return (a.quality - b.quality) * dir;
        case "severity":
          return ((SEV_RANK[a.severity] ?? 0) - (SEV_RANK[b.severity] ?? 0)) * dir;
        case "status":
          return ((STATUS_RANK[a.status] ?? 0) - (STATUS_RANK[b.status] ?? 0)) * dir;
        default:
          return a[sort.key].localeCompare(b[sort.key], "fr") * dir;
      }
    });
  }, [signals, query, status, severity, category, source, sort, t]);

  if (!data) return <Skeleton />;
  if (!data.available) return <Unavailable t={t} />;

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key ? { key, dir: (s.dir === 1 ? -1 : 1) as 1 | -1 } : { key, dir: 1 },
    );

  const onExport = () => {
    const blob = new Blob([JSON.stringify(data.signals, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tessera-signal-catalogue.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <CommandBar t={t} onExport={onExport} />

      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 xl:grid-cols-9">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} />
        ))}
      </div>

      <FilterStrip
        t={t}
        data={data}
        query={query}
        onQuery={setQuery}
        status={status}
        onStatus={setStatus}
        severity={severity}
        onSeverity={setSeverity}
        category={category}
        onCategory={setCategory}
        source={source}
        onSource={setSource}
        count={rows.length}
        total={signals.length}
      />

      <SignalTable
        t={t}
        tt={tt}
        rows={rows}
        sort={sort}
        onSort={toggleSort}
        selected={selected}
        onSelect={setSelected}
      />

      <Footer t={t} data={data} />

      {selected ? <SignalDrawer t={t} signal={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({ t, onExport }: { t: T; onExport: () => void }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="min-w-0 flex-1 truncate text-xs text-[var(--tessera-text-muted)]">
        {t("subtitle")}
      </p>
      <Button
        size="sm"
        variant="outline"
        onClick={onExport}
        className="h-9 shrink-0 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
      >
        <Download className="h-4 w-4" /> {t("actions.exportCatalogue")}
      </Button>
    </section>
  );
}

/** ⓘ for a signal-catalogue KPI, reading signalCatalogue.explain.<k>. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("signalCatalogue.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te.has(`${k}.how`) ? te(`${k}.how`) : undefined}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

function CompactKpi({ kpi, label }: { kpi: Data["kpis"][number]; label: string }) {
  return (
    <div className="flex h-[88px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <p className="flex items-center gap-1 text-[0.62rem] font-medium text-[var(--tessera-text-muted)]">
        <Truncate full={label} className="min-w-0">
          {label}
        </Truncate>
        <ExplainInfo k={kpi.key} title={label} />
      </p>
      <p className="mt-0.5 text-[1.3rem] font-semibold leading-none text-[var(--tessera-text-strong)]">
        {kpi.value}
      </p>
      <Truncate
        as="p"
        full={kpi.sub}
        className="mt-0.5 text-[0.56rem] text-[var(--tessera-text-muted)]"
      >
        {kpi.sub}
      </Truncate>
      <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
    </div>
  );
}

function FilterStrip({
  t,
  data,
  query,
  onQuery,
  status,
  onStatus,
  severity,
  onSeverity,
  category,
  onCategory,
  source,
  onSource,
  count,
  total,
}: {
  t: T;
  data: Data;
  query: string;
  onQuery: (v: string) => void;
  status: string;
  onStatus: (v: string) => void;
  severity: string;
  onSeverity: (v: string) => void;
  category: string;
  onCategory: (v: string) => void;
  source: string;
  onSource: (v: string) => void;
  count: number;
  total: number;
}) {
  const statuses = useMemo(() => [...new Set(data.signals.map((s) => s.status))], [data.signals]);
  const severities = useMemo(
    () =>
      [...new Set(data.signals.map((s) => s.severity))].sort(
        (a, b) => (SEV_RANK[a] ?? 0) - (SEV_RANK[b] ?? 0),
      ),
    [data.signals],
  );
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="relative min-w-[180px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          aria-label={t("filters.search")}
          placeholder={t("filters.search")}
          className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[#2e72d2]"
        />
      </div>
      <FilterSelect
        label={t("filters.status")}
        value={status}
        onChange={onStatus}
        options={statuses.map((s) => ({ value: s, label: t(`status.${s}`) }))}
        allLabel={t("filters.all")}
      />
      <FilterSelect
        label={t("filters.severity")}
        value={severity}
        onChange={onSeverity}
        options={severities.map((s) => ({ value: s, label: t(`severity.${s}`) }))}
        allLabel={t("filters.all")}
      />
      <FilterSelect
        label={t("filters.category")}
        value={category}
        onChange={onCategory}
        options={data.categories.map((c) => ({ value: c, label: t(`category.${c}`) }))}
        allLabel={t("filters.all")}
      />
      <FilterSelect
        label={t("filters.source")}
        value={source}
        onChange={onSource}
        options={data.sources.map((s) => ({ value: s, label: translated(t, "sourceValue", s) }))}
        allLabel={t("filters.all")}
      />
      <span className="shrink-0 text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
        {count}/{total}
      </span>
    </section>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  allLabel: string;
}) {
  return (
    <label className="relative shrink-0">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 cursor-pointer appearance-none rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-3 pr-8 text-xs text-[var(--tessera-text)] outline-none hover:border-[#2e72d2] focus:border-[#2e72d2]"
      >
        <option value="all">
          {label}: {allLabel}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronsUpDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--tessera-fg-info)]" />
    </label>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

function qualityTone(q: number): string {
  return q >= 90 ? "bg-emerald-400" : q >= 75 ? "bg-amber-400" : "bg-red-400";
}

function SignalTable({
  t,
  tt,
  rows,
  sort,
  onSort,
  selected,
  onSelect,
}: {
  t: T;
  tt: TT;
  rows: ScSignal[];
  sort: { key: SortKey; dir: 1 | -1 };
  onSort: (key: SortKey) => void;
  selected: ScSignal | null;
  onSelect: (s: ScSignal) => void;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on filter/sort/size change
  useEffect(() => setPage(1), [total, perPage, sort.key, sort.dir]);
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * perPage;
  const pageRows = rows.slice(start, start + perPage);
  return (
    <div
      data-testid="signals-table"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[940px] table-fixed border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c, idx) => (
                <th
                  key={c.key}
                  style={{ width: c.w }}
                  className={cn("py-1.5 font-medium", idx === 0 ? "pl-5 pr-2" : "px-2")}
                >
                  {c.sort ? (
                    <button
                      type="button"
                      onClick={() => onSort(c.sort as SortKey)}
                      aria-sort={
                        sort.key === c.sort ? (sort.dir === 1 ? "ascending" : "descending") : "none"
                      }
                      className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-[var(--tessera-text)]"
                    >
                      {t(`col.${c.key}`)}
                      {sort.key === c.sort ? (
                        sort.dir === 1 ? (
                          <SortAsc className="h-3 w-3 text-[var(--tessera-fg-info)]" />
                        ) : (
                          <SortDesc className="h-3 w-3 text-[var(--tessera-fg-info)]" />
                        )
                      ) : (
                        <ChevronsUpDown className="h-3 w-3 opacity-40" />
                      )}
                    </button>
                  ) : (
                    t(`col.${c.key}`)
                  )}
                </th>
              ))}
              <th className="w-28 px-2 py-1.5" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {pageRows.map((s) => {
              const active = s.id === selected?.id;
              return (
                <tr
                  key={s.id}
                  onClick={() => onSelect(s)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(s);
                    }
                  }}
                  tabIndex={0}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                  role="button"
                  aria-label={translated(t, "name", s.name)}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors last:border-0 hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="py-1.5 pl-5 pr-2">
                    <Truncate
                      full={translated(t, "name", s.name)}
                      className="text-[0.7rem] font-medium text-[var(--tessera-text)]"
                    >
                      {translated(t, "name", s.name)}
                    </Truncate>
                    <Truncate
                      full={s.id}
                      className="font-mono text-[0.56rem] text-[var(--tessera-text-muted)]"
                    >
                      {s.id}
                    </Truncate>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={t(`category.${s.category}`)}>
                      {t(`category.${s.category}`)}
                    </Truncate>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={translated(t, "sourceValue", s.source)}>
                      {translated(t, "sourceValue", s.source)}
                    </Truncate>
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={SEV_BADGE[s.severity]}>{t(`severity.${s.severity}`)}</Badge>
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={STATUS_BADGE[s.status]}>{t(`status.${s.status}`)}</Badge>
                  </td>
                  <td className="px-2 py-1.5">
                    <div className="flex items-center gap-1.5">
                      <div className="h-[4px] overflow-hidden w-10 shrink-0 rounded-full bg-[var(--tessera-border)]">
                        <div
                          className={cn("h-full rounded-full", qualityTone(s.quality))}
                          style={{ width: `${s.quality}%` }}
                        />
                      </div>
                      <span className="tabular-nums text-[var(--tessera-text-muted)]">
                        {s.quality}%
                      </span>
                    </div>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={s.last_activity}>{s.last_activity}</Truncate>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={translated(t, "ownerValue", s.owner)}>
                      {translated(t, "ownerValue", s.owner)}
                    </Truncate>
                  </td>
                  <td className="px-2 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    <Truncate full={s.modified}>{s.modified}</Truncate>
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="flex items-center justify-end gap-1 whitespace-nowrap">
                      <span className="text-[0.66rem] text-[var(--tessera-fg-info)] opacity-0 transition-opacity group-hover:opacity-100">
                        {tt("rowOpen")}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[var(--tessera-fg-info)]" />
                    </span>
                  </td>
                </tr>
              );
            })}
            {total === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length + 1}
                  className="px-2 py-6 text-center text-[0.7rem] text-[var(--tessera-text-muted)]"
                >
                  {tt("empty")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <TablePagination
        tt={tt}
        page={safePage}
        totalPages={totalPages}
        start={total === 0 ? 0 : start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
        accent={ACCENT}
      />
    </div>
  );
}

// Shared connaissances-style pagination footer (reused across cockpit tables).
function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(5, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, Math.max(1, totalPages - span + 1));
  return Array.from({ length: span }, (_, i) => first + i);
}

function TablePagination({
  tt,
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
  accent,
}: {
  tt: TT;
  page: number;
  totalPages: number;
  start: number;
  end: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
  accent: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {tt("summary", { start, end, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          aria-label={tt("prev")}
          onClick={() => onPage(Math.max(1, page - 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        {pageWindow(page, totalPages).map((n) => (
          <button
            key={n}
            type="button"
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
            style={
              n === page ? { borderColor: `${accent}99`, background: `${accent}26` } : undefined
            }
            className={cn(
              "flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-[0.72rem] tabular-nums",
              n === page
                ? "font-medium text-[var(--tessera-text-strong)]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {n}
          </button>
        ))}
        <button
          type="button"
          disabled={page >= totalPages}
          aria-label={tt("next")}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
      <label className="flex items-center gap-2">
        <span>{tt("perPage")}</span>
        <select
          value={perPage}
          onChange={(e) => onPerPage(Number(e.target.value))}
          className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.72rem] text-[var(--tessera-text)] focus:outline-none"
        >
          {ROWS_PER_PAGE_OPTS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

// ── drawer ───────────────────────────────────────────────────────────────────

function SignalDrawer({ t, signal, onClose }: { t: T; signal: ScSignal; onClose: () => void }) {
  const d = signal.detail;
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  const [shown, setShown] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const FOCUSABLE = 'button, a[href], select, input, [tabindex]:not([tabindex="-1"])';
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    return () => opener?.focus?.();
  }, []);
  const onTrapKey = (event: ReactKeyboardEvent<HTMLDialogElement>) => {
    if (event.key !== "Tab" || !dialogRef.current) return;
    const f = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
    const first = f[0];
    const last = f[f.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  useEffect(() => {
    const measure = () => {
      const m = document.querySelector("main");
      if (!m) return;
      const mr = m.getBoundingClientRect();
      const c = document.querySelector("[data-shell-content]") ?? m;
      const cr = c.getBoundingClientRect();
      setRect({ top: mr.top, left: cr.left, width: cr.width, height: mr.bottom - mr.top });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  useEffect(() => {
    setShown(true);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed z-50 flex justify-end overflow-hidden bg-[#020817]/70 py-2.5 pl-2.5 backdrop-blur-[2px]"
      style={rect ?? { inset: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <dialog
        ref={dialogRef}
        open
        aria-modal="true"
        aria-label={translated(t, "name", signal.name)}
        onKeyDown={onTrapKey}
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        className={cn(
          "static m-0 block h-full w-full max-w-[460px] bg-transparent p-0 transition-transform duration-200 ease-out",
          shown ? "translate-x-0" : "translate-x-full",
        )}
      >
        <aside
          data-testid="signal-detail"
          className="flex h-full w-full min-w-0 flex-col gap-3 overflow-y-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <Truncate
                as="p"
                full={translated(t, "name", d.name)}
                className="text-sm font-semibold text-[var(--tessera-text-strong)]"
              >
                {translated(t, "name", d.name)}
              </Truncate>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {d.name} · {d.id}
                </span>
                <Badge className={SEV_BADGE[d.severity]}>{t(`severity.${d.severity}`)}</Badge>
                <Badge className={STATUS_BADGE[d.status]}>{t(`status.${d.status}`)}</Badge>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("detail.moreDetails")}
              className="shrink-0 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text)]">
            {d.description}
          </p>

          <Section title={t("detail.secDefinition")}>
            <RowList rows={d.definition} />
          </Section>

          <Section title={t("detail.secPerformance")}>
            <RowList rows={d.performance} />
          </Section>

          {d.guard.length > 0 ? (
            <Section title={t("detail.secGuard")}>
              <RowList rows={d.guard} mono />
            </Section>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <Section title={t("detail.byLanguage")}>
              <BarRow bars={d.distribution} />
            </Section>
            <Section title={t("detail.outcomeTitle")}>
              <BarRow bars={d.outcome} />
            </Section>
          </div>

          {d.tags.length > 0 ? (
            <Section title={t("detail.secTags")}>
              <div className="flex flex-wrap gap-1">
                {d.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </Section>
          ) : null}

          <Section title={t("detail.secUsage")}>
            <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("detail.loggedBy", { n: d.usage.logged_by })}
            </p>
            <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("detail.monitors", { n: d.usage.monitors })}
            </p>
          </Section>
        </aside>
      </dialog>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)]/40 p-2.5">
      <p className="mb-1.5 text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {title}
      </p>
      {children}
    </div>
  );
}

function RowList({ rows, mono }: { rows: { label: string; value: string }[]; mono?: boolean }) {
  return (
    <dl className="flex flex-col gap-1 text-[0.66rem]">
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-2">
          <dt className="shrink-0 text-[var(--tessera-text-muted)]">{r.label}</dt>
          <Truncate
            as="dd"
            full={r.value}
            className={cn(
              "min-w-0 text-right text-[var(--tessera-text)]",
              mono && "font-mono text-[0.62rem]",
            )}
          >
            {r.value}
          </Truncate>
        </div>
      ))}
    </dl>
  );
}

function BarRow({ bars }: { bars: { label: string; count: number; color: string }[] }) {
  const max = Math.max(...bars.map((b) => b.count), 1);
  return (
    <div className="flex h-[70px] items-end gap-2">
      {bars.map((b) => (
        <div key={b.label} className="flex flex-1 flex-col items-center gap-0.5">
          <span className="text-[0.5rem] tabular-nums text-[var(--tessera-text-muted)]">
            {b.count}
          </span>
          <div
            className="w-full rounded-t-sm"
            style={{ height: `${Math.max(4, (b.count / max) * 100)}%`, background: b.color }}
          />
          <span className="text-[0.5rem] text-[var(--tessera-text-muted)]">{b.label}</span>
        </div>
      ))}
    </div>
  );
}

function Footer({ t, data }: { t: T; data: Data }) {
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span>{t("footer.total", { n: data.footer.total })}</span>
      <span>{t("footer.source", { src: data.footer.source })}</span>
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.58rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function Skeleton() {
  return (
    <div className="flex flex-col gap-3 pb-2">
      <div className="h-[54px] animate-pulse rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]" />
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 xl:grid-cols-9">
        {["a", "b", "c", "d", "e", "f", "g", "h", "i"].map((k) => (
          <div
            key={k}
            className="h-[88px] animate-pulse rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
          />
        ))}
      </div>
      <div className="h-[320px] animate-pulse rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]" />
    </div>
  );
}

function Unavailable({ t }: { t: T }) {
  return (
    <div className="flex min-h-[200px] flex-1 items-center justify-center rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-8 text-center text-sm text-[var(--tessera-text-muted)]">
      {t("subtitle")}
    </div>
  );
}

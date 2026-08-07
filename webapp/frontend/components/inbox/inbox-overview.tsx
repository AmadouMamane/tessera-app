"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Layers,
  RefreshCcw,
  Search,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchInboxOverview, mutateInboxItem } from "@/lib/api/client";
import type { InboxOverview as InboxData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const ALL = "all";
// Status badge click cycles through the lifecycle; map UI -> backend keys.
const NEXT_STATUS: Record<string, string> = {
  todo: "in_progress",
  in_progress: "resolved",
  resolved: "todo",
};
const STATUS_TO_BACKEND: Record<string, string> = {
  todo: "todo",
  in_progress: "progress",
  resolved: "done",
};

const PRIORITY: Record<string, string> = {
  urgent: "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
  high: "border-amber-500/30 bg-amber-500/15 text-[var(--tessera-fg-warning)]",
  medium: "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]",
  low: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
};
// Severity rank so the Priority column sorts by urgency, not alphabetically.
const PRIO_RANK: Record<string, number> = { urgent: 0, high: 1, medium: 2, low: 3 };
const STATUS: Record<string, string> = {
  todo: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  in_progress: "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]",
  waiting: "border-amber-500/30 bg-amber-500/15 text-[var(--tessera-fg-warning)]",
  resolved: "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]",
};
const SLA_TONE: Record<string, string> = {
  crit: "text-[var(--tessera-fg-danger)]",
  warn: "text-[var(--tessera-fg-warning)]",
  ok: "text-[var(--tessera-fg-success)]",
};

const ROWS_PER_PAGE_OPTS = [10, 25, 50];
const COLS = ["priority", "type", "title", "source", "assignee", "sla", "due", "status"] as const;
// Proportional fixed widths (table-fixed): Title is the wide identifier column.
const COL_W = ["9%", "11%", "25%", "16%", "12%", "9%", "9%", "9%"];

type T = ReturnType<typeof useTranslations<"inbox">>;
type Data = InboxData;
type Item = Data["items"][number];
type SortDir = "asc" | "desc";

const SORT_VALUE: ((it: Item) => string | number)[] = [
  (it) => PRIO_RANK[it.priority] ?? 9,
  (it) => it.type.toLowerCase(),
  (it) => it.title.toLowerCase(),
  (it) => it.source.toLowerCase(),
  (it) => it.assignee.toLowerCase(),
  (it) => it.sla.toLowerCase(),
  (it) => it.due.toLowerCase(),
  (it) => it.status.toLowerCase(),
];

export function InboxOverview() {
  const t = useTranslations("inbox");
  const locale = useLocale();
  const qc = useQueryClient();
  const { data, isError, isFetching, refetch } = useQuery({
    queryKey: ["inbox-overview", locale],
    queryFn: ({ signal }) => fetchInboxOverview(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [search, setSearch] = useState("");
  const [fPriority, setFPriority] = useState(ALL);
  const [fStatus, setFStatus] = useState(ALL);
  const [fType, setFType] = useState(ALL);
  const [fAgent, setFAgent] = useState(ALL);
  // WF-01 (rail norm): the selected case derives from the URL (`?item=`),
  // never from local state — a case detail is deep-linkable and shareable.
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selected = searchParams.get("item");
  const setSelected = (itemId: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (itemId) {
      params.set("item", itemId);
    } else {
      params.delete("item");
    }
    const qs = params.toString();
    router.replace((qs ? `${pathname}?${qs}` : pathname) as Route);
  };
  const mutate = useMutation({
    mutationFn: mutateInboxItem,
    // The key must match the query's — `["inbox-overview", locale]`. Writing the
    // locale-less key put the fresh payload in a cache entry nothing reads, so a cycled
    // status only appeared after the 30 s refetch or a reload.
    onSuccess: (fresh) => qc.setQueryData(["inbox-overview", locale], fresh),
  });

  const items = data?.items ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter(
      (it) =>
        (q === "" || it.title.toLowerCase().includes(q) || it.id.toLowerCase().includes(q)) &&
        (fPriority === ALL || it.priority === fPriority) &&
        (fStatus === ALL || it.status === fStatus) &&
        (fType === ALL || it.type === fType) &&
        (fAgent === ALL || it.agent_id === fAgent),
    );
  }, [items, search, fPriority, fStatus, fType, fAgent]);

  const detail = selected ? (items.find((it) => it.id === selected) ?? null) : null;

  if (isError && !data) {
    return <QueryErrorState onRetry={() => void refetch()} retrying={isFetching} />;
  }

  if (!data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  const cycle = (id: string, status: string) =>
    mutate.mutate({ item_id: id, status: STATUS_TO_BACKEND[NEXT_STATUS[status] ?? "todo"] });

  return (
    <div className="flex flex-col gap-2.5 text-[var(--tessera-text)]">
      <Rail t={t} data={data} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-8">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} vs={t("delta.vsHier")} />
        ))}
      </div>

      <FilterStrip
        t={t}
        data={data}
        search={search}
        setSearch={setSearch}
        fPriority={fPriority}
        setFPriority={setFPriority}
        fStatus={fStatus}
        setFStatus={setFStatus}
        fType={fType}
        setFType={setFType}
        fAgent={fAgent}
        setFAgent={setFAgent}
        count={filtered.length}
      />

      <TaskTable t={t} rows={filtered} selected={selected} onSelect={setSelected} />

      <div className="grid min-w-0 items-start gap-2.5 md:grid-cols-3">
        <ByType t={t} data={data} />
        <Sla t={t} data={data} />
        <Activity t={t} data={data} />
      </div>

      <Footer t={t} data={data} />

      {detail ? (
        <InboxDrawer
          t={t}
          item={detail}
          busy={mutate.isPending}
          onClose={() => setSelected(null)}
          onCycle={() => cycle(detail.id, detail.status)}
        />
      ) : null}
    </div>
  );
}

// ── rail ─────────────────────────────────────────────────────────────────────

function Rail({ t, data }: { t: T; data: Data }) {
  const tc = useTranslations("common");
  const r = data.rail;
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="flex items-center gap-1.5 font-medium text-[var(--tessera-green)]">
        <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--tessera-green)]" />{" "}
        {t("rail.live")}
      </span>
      <span className="text-[var(--tessera-text-muted)]">{t("rail.queue")}</span>
      <Sep />
      <span className="text-[var(--tessera-text-muted)]">{t("rail.realtime")}</span>
      <Sep />
      <span className="text-[var(--tessera-text-muted)]">
        {t("rail.period")} : <span className="text-[var(--tessera-text)]">{r.period}</span>
      </span>
      <Sep />
      <span className="text-[var(--tessera-text-muted)]">
        {t("rail.updated")} :{" "}
        <span className="tabular-nums text-[var(--tessera-text)]">{r.updated}</span>
      </span>
      <div className="ml-auto flex items-center gap-2">
        <span title={tc("notWired")}>
          <button
            type="button"
            disabled
            className="flex h-8 cursor-not-allowed items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[var(--tessera-text-muted)] opacity-50"
          >
            <RefreshCcw className="h-3.5 w-3.5" /> {t("rail.replay")}
          </button>
        </span>
        <span title={tc("notWired")}>
          <Button
            size="sm"
            disabled
            className="h-8 gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/60 px-3 text-xs text-[var(--tessera-fg-accent)]"
          >
            <Layers className="h-3.5 w-3.5" /> {t("rail.bulk")}
          </Button>
        </span>
      </div>
    </section>
  );
}

function CompactKpi({ kpi, label, vs }: { kpi: Data["kpis"][number]; label: string; vs: string }) {
  const up = kpi.delta_label.trim().startsWith("+");
  const good = up === kpi.good_is_up;
  const te = useTranslations("inbox.explain");
  return (
    <div className="flex h-[96px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
        <span className="truncate">{label}</span>
        {te.has(`${kpi.key}.what`) ? (
          <MetricInfo
            title={label}
            what={te(`${kpi.key}.what`)}
            how={te.has(`${kpi.key}.how`) ? te(`${kpi.key}.how`) : undefined}
            source={te.has(`${kpi.key}.source`) ? te(`${kpi.key}.source`) : undefined}
            className="ml-auto"
          />
        ) : null}
      </p>
      <p className="mt-0.5 whitespace-nowrap text-[1.35rem] font-semibold leading-none text-[var(--tessera-text-strong)]">
        {kpi.value}
      </p>
      <p
        className={cn(
          "mt-0.5 text-[0.58rem] font-medium",
          good ? "text-[var(--tessera-green)]" : "text-[var(--tessera-fg-danger)]",
        )}
      >
        {kpi.delta_label} {vs}
      </p>
      <MetricSparkline
        className="mt-auto h-4 w-full"
        values={kpi.series}
        tone={kpi.good_is_up ? "success" : "danger"}
      />
    </div>
  );
}

// ── filter strip ─────────────────────────────────────────────────────────────

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <span className="relative flex h-9 shrink-0 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pr-7 pl-3 text-xs text-[var(--tessera-text-muted)]">
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none bg-transparent pr-1 text-[var(--tessera-text)] outline-none"
      >
        <option value={ALL} className="bg-[#0a1f33]">
          {label}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-[#0a1f33]">
            {o.label}
          </option>
        ))}
      </select>
      <ChevronRight className="pointer-events-none absolute right-2 h-3.5 w-3.5 rotate-90" />
    </span>
  );
}

function FilterStrip({
  t,
  data,
  search,
  setSearch,
  fPriority,
  setFPriority,
  fStatus,
  setFStatus,
  fType,
  setFType,
  fAgent,
  setFAgent,
  count,
}: {
  t: T;
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  fPriority: string;
  setFPriority: (v: string) => void;
  fStatus: string;
  setFStatus: (v: string) => void;
  fType: string;
  setFType: (v: string) => void;
  fAgent: string;
  setFAgent: (v: string) => void;
  count: number;
}) {
  const priorityOpts = ["urgent", "high", "medium", "low"].map((v) => ({
    value: v,
    label: t(`priority.${v}`),
  }));
  const statusOpts = ["todo", "in_progress", "resolved"].map((v) => ({
    value: v,
    label: t(`status.${v}`),
  }));
  const typeOpts = [...new Set(data.items.map((i) => i.type))].map((v) => ({
    value: v,
    label: t(`type.${v}`),
  }));
  // Ventilation control: the distinct agents whose own eval runs seeded this queue.
  const agentOpts = [...new Map(data.items.map((i) => [i.agent_id, i.agent])).entries()]
    .filter(([id]) => id)
    .map(([value, label]) => ({ value, label: label || value }));
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="relative min-w-[200px] flex-1">
        <Search className="-translate-y-1/2 pointer-events-none absolute top-1/2 left-3 h-4 w-4 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("filters.search")}
          aria-label={t("filters.search")}
          className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pr-3 pl-9 text-xs text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
        />
      </div>
      <FilterSelect
        label={t("filters.priority")}
        value={fPriority}
        options={priorityOpts}
        onChange={setFPriority}
      />
      <FilterSelect
        label={t("filters.type")}
        value={fType}
        options={typeOpts}
        onChange={setFType}
      />
      <FilterSelect
        label={t("filters.status")}
        value={fStatus}
        options={statusOpts}
        onChange={setFStatus}
      />
      {agentOpts.length > 1 ? (
        <FilterSelect
          label={t("filters.agent")}
          value={fAgent}
          options={agentOpts}
          onChange={setFAgent}
        />
      ) : null}
      <span className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)]">
        <Layers className="h-3.5 w-3.5" /> {count} / {data.total_items}
      </span>
    </section>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

function TaskTable({
  t,
  rows,
  selected,
  onSelect,
}: {
  t: T;
  rows: Item[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    if (sortCol === null) return rows;
    const get = SORT_VALUE[sortCol];
    if (!get) return rows;
    return [...rows].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortCol, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on filter/sort/size change
  useEffect(() => setPage(1), [total, perPage, sortCol, sortDir]);
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * perPage;
  const pageRows = sorted.slice(start, start + perPage);

  function toggleSort(i: number) {
    if (!SORT_VALUE[i]) return;
    if (i === sortCol) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(i);
      setSortDir("asc");
    }
  }

  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table
          data-premium-table="true"
          className="w-full min-w-[760px] table-fixed border-collapse text-left text-xs"
        >
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c, i) => (
                <th
                  key={c}
                  style={{ width: COL_W[i] }}
                  aria-sort={
                    sortCol === i ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className={cn("py-1.5 font-medium", i === 0 ? "pl-5 pr-2" : "px-2")}
                >
                  <button
                    type="button"
                    onClick={() => toggleSort(i)}
                    className={cn(
                      "inline-flex items-center gap-1 uppercase tracking-wide hover:text-[var(--tessera-text)]",
                      sortCol === i && "text-[var(--tessera-text)]",
                    )}
                  >
                    {t(`col.${c}`)}
                    {sortCol === i ? (
                      <span className="text-[0.7rem]">{sortDir === "asc" ? "▲" : "▼"}</span>
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
              <th className="w-28 px-2 py-1.5" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {pageRows.map((it) => {
              const active = it.id === selected;
              return (
                <tr
                  key={it.id}
                  // biome-ignore lint/a11y/useSemanticElements: a data row opens the detail drawer; keyboard + role provided.
                  role="button"
                  aria-haspopup="dialog"
                  tabIndex={0}
                  aria-label={it.title}
                  aria-pressed={active}
                  onClick={() => onSelect(it.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(it.id);
                    }
                  }}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors last:border-0 hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="py-2 pl-5 pr-2">
                    <Badge className={PRIORITY[it.priority]}>{t(`priority.${it.priority}`)}</Badge>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text-muted)]">
                    <span className="block truncate" title={t(`type.${it.type}`)}>
                      {t(`type.${it.type}`)}
                    </span>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text)]">
                    <Truncate full={it.title}>
                      {it.title}
                      {it.agent ? (
                        <span className="ml-1.5 rounded bg-[var(--tessera-muted)] px-1 py-px text-[0.52rem] text-[var(--tessera-text-muted)]">
                          {it.agent}
                        </span>
                      ) : null}
                    </Truncate>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text-muted)]">
                    <Truncate>{it.source}</Truncate>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text-muted)]">
                    <Truncate>{it.assignee}</Truncate>
                  </td>
                  <td className={cn("px-2 py-2 font-medium tabular-nums", SLA_TONE[it.sla_tone])}>
                    {it.sla}
                  </td>
                  <td className="px-2 py-2 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    {it.due}
                  </td>
                  <td className="px-2 py-2">
                    <Badge className={STATUS[it.status]}>{t(`status.${it.status}`)}</Badge>
                  </td>
                  <td className="px-2 py-2">
                    <span className="flex items-center justify-end gap-1 whitespace-nowrap">
                      <span className="text-[0.66rem] text-[var(--tessera-fg-info)] opacity-0 transition-opacity group-hover:opacity-100">
                        {t("rowOpen")}
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
                  className="px-2 py-8 text-center text-[var(--tessera-text-muted)]"
                >
                  {t("noResults")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pagination
        t={t}
        page={safePage}
        totalPages={totalPages}
        start={total === 0 ? 0 : start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
      />
    </section>
  );
}

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(5, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, Math.max(1, totalPages - span + 1));
  return Array.from({ length: span }, (_, i) => first + i);
}

function Pagination({
  t,
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
}: {
  t: T;
  page: number;
  totalPages: number;
  start: number;
  end: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {t("page.summary", { start, end, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          aria-label={t("page.prev")}
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
            className={cn(
              "flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-[0.72rem] tabular-nums",
              n === page
                ? "border-[#87bfff]/60 bg-[#87bfff]/15 font-medium text-[var(--tessera-text-strong)]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {n}
          </button>
        ))}
        <button
          type="button"
          disabled={page >= totalPages}
          aria-label={t("page.next")}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
      <label className="flex items-center gap-2">
        <span>{t("page.perPage")}</span>
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

// ── detail drawer (right-entering overlay anchored to the content column) ──────

function InboxDrawer({
  t,
  item,
  busy,
  onClose,
  onCycle,
}: {
  t: T;
  item: Item;
  busy: boolean;
  onClose: () => void;
  onCycle: () => void;
}) {
  const fields: [string, ReactNode][] = [
    [t("col.type"), t(`type.${item.type}`)],
    ...(item.agent ? ([[t("filters.agent"), item.agent]] as [string, ReactNode][]) : []),
    [t("col.source"), item.source],
    [t("col.assignee"), item.assignee],
    [
      t("col.sla"),
      <span key="sla" className={cn("font-medium tabular-nums", SLA_TONE[item.sla_tone])}>
        {item.sla}
      </span>,
    ],
    [t("col.due"), item.due],
  ];

  return (
    <DetailDrawer onClose={onClose} title={item.title} subtitle={item.id} width="max-w-[440px]">
      <Badge className={PRIORITY[item.priority]}>{t(`priority.${item.priority}`)}</Badge>
      <div className="flex min-w-0 flex-col gap-3 text-[var(--tessera-text)]">
        <dl className="flex flex-col gap-2.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[0.74rem]">
          {fields.map(([label, value]) => (
            <div
              key={label}
              className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)]/40 pb-2 last:border-0 last:pb-0"
            >
              <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
              <dd className="min-w-0 truncate text-right font-medium">{value}</dd>
            </div>
          ))}
        </dl>

        {/* WF-01 — the journaled transitions of this case, each naming its
              verified author (ADR 0024). Honest empty when it never moved. */}
        <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
          <p className="text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {t("drawer.transitions")}
          </p>
          {item.transitions.length > 0 ? (
            <ol className="mt-1.5 flex flex-col gap-1.5 text-[0.68rem]">
              {item.transitions.map((r, i) => (
                <li
                  key={`${r.at}-${r.label}-${i}`}
                  className="flex items-baseline justify-between gap-2"
                >
                  <span className="min-w-0">
                    <span className="text-[var(--tessera-text)]">{r.label}</span>{" "}
                    <span className="text-[var(--tessera-text-muted)]">· {r.by}</span>
                  </span>
                  <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.at}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-1.5 text-[0.62rem] leading-snug text-[var(--tessera-text-muted)]">
              {t("drawer.transitionsEmpty")}
            </p>
          )}
        </div>

        <div className="mt-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
          <p className="text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {t("col.status")}
          </p>
          <span className="mt-1 inline-flex">
            <Badge className={STATUS[item.status]}>{t(`status.${item.status}`)}</Badge>
          </span>
          <button
            type="button"
            onClick={onCycle}
            disabled={busy}
            className="mt-3 flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-[0.7rem] font-medium text-white hover:bg-[#7c5cf5] disabled:opacity-50"
          >
            <RefreshCcw className="h-3.5 w-3.5" /> {t("cycleStatus")}
          </button>
          {item.href ? (
            <Link
              href={item.href}
              className="mt-2 flex h-9 w-full items-center justify-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 text-[0.7rem] font-medium text-[var(--tessera-fg-info)] hover:text-[var(--tessera-text-strong)]"
            >
              {t("openBusinessRun")} <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          ) : null}
        </div>
      </div>
    </DetailDrawer>
  );
}

// ── right-column panels (now full-width grid below the table) ──────────────────

function ByType({ t, data }: { t: T; data: Data }) {
  const sum = data.by_type.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <Panel title={t("zone.byType")}>
      <div className="flex items-center gap-3">
        <div className="relative h-[88px] w-[88px] shrink-0">
          <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle
              cx="36"
              cy="36"
              r={R}
              fill="none"
              stroke="var(--tessera-border)"
              strokeWidth="9"
            />
            {data.by_type.map((s) => {
              const frac = s.count / sum;
              const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
              off += frac;
              return (
                <circle
                  key={s.key}
                  cx="36"
                  cy="36"
                  r={R}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="9"
                  strokeDasharray={`${seg.dash} ${seg.gap}`}
                  strokeDashoffset={seg.o}
                />
              );
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-base font-semibold tabular-nums text-[var(--tessera-text-strong)]">
              {data.by_type_total}
            </span>
            <span className="text-[0.46rem] uppercase text-[var(--tessera-text-muted)]">Total</span>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
          {data.by_type.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                {t(`type.${s.key}`)}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {s.count} ({s.pct}%)
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function Sla({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.sla_buckets.map((b) => b.count), 1);
  return (
    <Panel title={t("zone.sla")}>
      <ul className="flex flex-col gap-2">
        {data.sla_buckets.map((b) => (
          <li key={b.key} className="flex items-center gap-2 text-[0.68rem]">
            <span className="w-16 shrink-0 text-[var(--tessera-text)]">{t(`sla.${b.key}`)}</span>
            <div className="h-[4px] overflow-hidden flex-1 rounded-full bg-[var(--tessera-border)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(b.count / max) * 100}%`, background: b.color }}
              />
            </div>
            <span className="w-5 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {b.count}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Activity({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.activity")}>
      <ul className="flex flex-col gap-1.5">
        {data.recent_activity.map((a, i) => (
          <li key={`${a.time}-${a.action}-${i}`} className="flex items-center gap-2 text-[0.66rem]">
            <CheckCircle2 className="h-3 w-3 shrink-0 text-[var(--tessera-fg-success)]" />
            <span className="font-medium text-[var(--tessera-text)]">{a.actor}</span>
            <Truncate className="min-w-0 flex-1 text-[var(--tessera-text-muted)]">
              {a.action}
            </Truncate>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">{a.time}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Panel({
  title,
  action,
  children,
}: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div
      data-slot="card"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="min-w-0 truncate text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
          {title}
        </h3>
        {action}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.56rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function Sep() {
  return <span className="hidden text-[var(--tessera-border-strong)] sm:inline">·</span>;
}

function Footer({ t, data }: { t: T; data: Data }) {
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span>{t("footer.total", { n: data.footer.total })}</span>
      <span>{t("footer.source", { src: data.footer.source })}</span>
    </footer>
  );
}

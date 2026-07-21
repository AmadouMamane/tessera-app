"use client";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Eye,
  FileSignature,
  Layers,
  type LucideIcon,
  PlusCircle,
  Search,
  StickyNote,
  UserPlus,
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

import {
  FilterDropdown,
  ResetButton,
  downloadBlob,
  toCsv,
} from "@/components/agent/agent-subtab-shared";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchAgentAFaire, mutateAFaireItem } from "@/lib/api/client";
import type { AgentAFaire as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type TaskT = NonNullable<Data["table"]>["tasks"][number];
type DetailT = NonNullable<Data["details"]>[number];
type T = ReturnType<typeof useTranslations<"agentAFaire">>;
type SortDir = "asc" | "desc";

const SPARK: Record<string, string> = {
  red: "#f87171",
  teal: "#34d399",
  amber: "#e0a23a",
  green: "#34d399",
};
const PRIO_TONE: Record<string, string> = {
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
  high: "border-orange-500/30 bg-orange-500/15 text-orange-300",
  mod: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  low: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
// Severity rank so the Priority column sorts by urgency, not alphabetically.
const PRIO_RANK: Record<string, number> = { crit: 0, high: 1, mod: 2, low: 3 };
const STATUS_TONE: Record<string, string> = {
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
  todo: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  progress: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  done: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const SLA_TONE: Record<string, string> = {
  crit: "text-red-300",
  warn: "text-amber-300",
  ok: "text-emerald-300",
};
const EVENT_DOT: Record<string, string> = {
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
  crit: "bg-red-400",
};

const ROWS_PER_PAGE_OPTS = [10, 25, 50];
// Proportional fixed widths (table-fixed): the Title column is the wide identifier
// column; numeric/status columns stay narrow. Index-keyed to the backend columns
// (priority, type, title, source, assignee, sla, due, status).
const COL_W = ["9%", "11%", "25%", "16%", "12%", "9%", "9%", "9%"];
// Which columns sort, and how to extract a comparable value from a task.
const SORT_VALUE: ((it: TaskT) => string | number)[] = [
  (it) => PRIO_RANK[it.prio_tone] ?? 9,
  (it) => it.type.toLowerCase(),
  (it) => it.title.toLowerCase(),
  (it) => it.source.toLowerCase(),
  (it) => it.assignee.toLowerCase(),
  (it) => it.sla.toLowerCase(),
  (it) => it.due.toLowerCase(),
  (it) => it.status.toLowerCase(),
];

// Client-side filter dimensions over the task rows. Tone keys are used where a
// locale-independent key exists (prio_tone, status_tone); type/assignee filter
// on the raw payload string. "all" disables a dimension.
type Filters = {
  prio: string;
  type: string;
  status: string;
  assignee: string;
  slaRisk: boolean;
};
const ALL_FILTERS: Filters = {
  prio: "all",
  type: "all",
  status: "all",
  assignee: "all",
  slaRisk: false,
};
// Saved views, index-keyed to the backend `filters.views` order: all cases /
// urgent / SLA at risk / assigned to me ("Moi" is the literal the assign
// mutation writes, whatever the locale).
const VIEW_PRESETS: Filters[] = [
  ALL_FILTERS,
  { ...ALL_FILTERS, prio: "crit" },
  { ...ALL_FILTERS, slaRisk: true },
  { ...ALL_FILTERS, assignee: "Moi" },
];
const sameFilters = (a: Filters, b: Filters) =>
  a.prio === b.prio &&
  a.type === b.type &&
  a.status === b.status &&
  a.assignee === b.assignee &&
  a.slaRisk === b.slaRisk;

export function AgentAFaire() {
  const t = useTranslations("agentAFaire");
  const locale = useLocale();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["agent-a-faire", locale],
    queryFn: ({ signal }) => fetchAgentAFaire(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Filters>(ALL_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const mutate = useMutation({
    mutationFn: (body: { item_id: string; status?: string; assignee?: string }) =>
      mutateAFaireItem({ ...body, lang: locale }),
    onSuccess: (fresh) => qc.setQueryData(["agent-a-faire", locale], fresh),
  });

  const tasks = data?.table?.tasks ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tasks.filter((it) => {
      if (
        q !== "" &&
        !(
          it.title.toLowerCase().includes(q) ||
          it.type.toLowerCase().includes(q) ||
          it.source.toLowerCase().includes(q) ||
          it.ref.toLowerCase().includes(q)
        )
      )
        return false;
      if (filters.prio !== "all" && it.prio_tone !== filters.prio) return false;
      if (filters.type !== "all" && it.type !== filters.type) return false;
      if (filters.status !== "all" && it.status_tone !== filters.status) return false;
      if (filters.assignee !== "all" && it.assignee !== filters.assignee) return false;
      if (filters.slaRisk && it.sla_tone === "ok") return false;
      return true;
    });
  }, [tasks, search, filters]);

  const details = data?.details ?? [];
  // The drawer opens only on an explicit row selection (Sources idiom).
  const detail = selected ? (details.find((d) => d.key === selected) ?? null) : null;

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  const setStatus = (status: string) => {
    if (detail?.selected.key) mutate.mutate({ item_id: detail.selected.key, status });
  };
  const assignMe = () => {
    if (detail?.selected.key) mutate.mutate({ item_id: detail.selected.key, assignee: "Moi" });
  };

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <Rail data={data} />
      <Timeline data={data} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4 xl:grid-cols-8">
        {(data.kpis ?? []).map((k) => (
          <Kpi key={k.key} kpi={k} />
        ))}
      </div>

      <FilterStrip
        data={data}
        tasks={tasks}
        search={search}
        setSearch={setSearch}
        filters={filters}
        setFilters={setFilters}
        count={filtered.length}
      />

      <TaskTable t={t} data={data} tasks={filtered} selected={selected} onSelect={setSelected} />

      <div className="grid min-w-0 items-start gap-2.5 md:grid-cols-2 xl:grid-cols-4">
        <Donut data={data} />
        <Sla data={data} />
        <Quick t={t} data={data} />
        <Activity data={data} />
      </div>

      <Footer data={data} />

      {detail ? (
        <TaskDrawer
          t={t}
          data={data}
          detail={detail}
          busy={mutate.isPending}
          onClose={() => setSelected(null)}
          onTake={() => setStatus("progress")}
          onResolve={() => setStatus("done")}
          onAssign={assignMe}
        />
      ) : null}
    </div>
  );
}

function Rail({ data }: { data: Data }) {
  const tc = useTranslations("common");
  const r = data.rail;
  if (!r) return null;
  return (
    <section className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-[#5b4bbd]/40 bg-[var(--tessera-surface)] px-3.5 py-2 text-xs">
      <span className="flex items-center gap-1.5 font-medium text-emerald-300">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" /> {r.live}
      </span>
      {r.segments.map((s) => (
        <span key={s} className="flex items-center gap-3 text-[var(--tessera-text-muted)]">
          <span className="text-[var(--tessera-border-strong)]">·</span> {s}
        </span>
      ))}
      <span className="ml-auto flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[var(--tessera-text-muted)]">
        {r.period}
      </span>
      <span className="tabular-nums text-[var(--tessera-text)]">{r.updated}</span>
      <span className="flex items-center gap-1 text-emerald-300">
        <ArrowUpRight className="h-3.5 w-3.5" /> {r.now}
      </span>
      <span className="flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[var(--tessera-text-muted)]">
        {r.scope}
      </span>
      <span title={tc("notWired")}>
        <button
          type="button"
          disabled
          className="flex h-8 cursor-not-allowed items-center gap-1.5 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/60 px-3 text-[#c4b5fd] opacity-50"
        >
          <Layers className="h-3.5 w-3.5" /> {r.bulk}
        </button>
      </span>
    </section>
  );
}

function Timeline({ data }: { data: Data }) {
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <section className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-2">
      <span className="flex items-center gap-1">
        <span className="text-[0.6rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {tl.title}
        </span>
        <ExplainInfo k="timeline" title={tl.title} />
      </span>
      {tl.events.map((e, i) => (
        <span key={`${e.time}-${e.ref}-${i}`} className="flex items-center gap-2">
          <span className={cn("h-1.5 w-1.5 rounded-full", EVENT_DOT[e.tone] ?? "bg-slate-400")} />
          <span className="text-[0.68rem]">
            <span className="tabular-nums text-[var(--tessera-text-muted)]">{e.time}</span>{" "}
            <span className="text-[var(--tessera-text)]">{e.label}</span>{" "}
            <span className="font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
              {e.ref}
            </span>
          </span>
        </span>
      ))}
    </section>
  );
}

/** ⓘ for an A-faire metric, reading agentAFaire.explain.<k>.{what,how,source?}. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("agentAFaire.explain");
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

function Kpi({ kpi }: { kpi: NonNullable<Data["kpis"]>[number] }) {
  return (
    <div className="flex h-[96px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 text-[0.62rem] font-medium text-[var(--tessera-text-muted)]">
        <Truncate full={kpi.label} className="min-w-0">
          {kpi.label}
        </Truncate>
        <ExplainInfo k={kpi.key} title={kpi.label} />
      </p>
      <p className="mt-0.5 whitespace-nowrap text-[1.3rem] font-semibold leading-none text-white">
        {kpi.value}
      </p>
      <p
        className={cn(
          "mt-0.5 text-[0.56rem] font-medium",
          kpi.good ? "text-emerald-400" : "text-red-300",
        )}
      >
        {kpi.delta}
      </p>
      <Spark className="mt-auto" values={kpi.series} color={SPARK[kpi.tone] ?? "#8b7cf0"} />
    </div>
  );
}

function Spark({
  values,
  color,
  className,
}: { values: number[]; color: string; className?: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 80;
  const H = 18;
  const d = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * W;
      const y = H - ((v - min) / span) * H;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className={cn("h-4 w-full", className)}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={d}
        fill="none"
        stroke={color}
        strokeWidth="1.4"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Horizontal filter strip (Sources idiom): wired search + REAL selects whose
// options derive from the live rows, saved-view preset pills, reset, count.
// The select order is index-keyed to the backend contract: priority, type,
// status, assignee — never matched by (localized) label.
function FilterStrip({
  data,
  tasks,
  search,
  setSearch,
  filters,
  setFilters,
  count,
}: {
  data: Data;
  tasks: TaskT[];
  search: string;
  setSearch: (v: string) => void;
  filters: Filters;
  setFilters: (f: Filters) => void;
  count: number;
}) {
  const f = data.filters;
  const options = useMemo(() => {
    const uniq = (pairs: [string, string][]) => {
      const seen = new Map<string, string>();
      for (const [value, label] of pairs) if (!seen.has(value)) seen.set(value, label);
      return [...seen.entries()].map(([value, label]) => ({ value, label }));
    };
    return {
      prio: uniq(tasks.map((it) => [it.prio_tone, it.priority] as [string, string])).sort(
        (a, b) => (PRIO_RANK[a.value] ?? 9) - (PRIO_RANK[b.value] ?? 9),
      ),
      type: uniq(tasks.map((it) => [it.type, it.type] as [string, string])),
      status: uniq(tasks.map((it) => [it.status_tone, it.status] as [string, string])),
      assignee: uniq(tasks.map((it) => [it.assignee, it.assignee] as [string, string])),
    };
  }, [tasks]);
  if (!f) return null;
  const dims = ["prio", "type", "status", "assignee"] as const;
  const touched = !sameFilters(filters, ALL_FILTERS) || search.trim() !== "";
  return (
    <section className="flex min-h-[54px] flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="relative min-w-[200px] flex-1">
        <Search className="-translate-y-1/2 pointer-events-none absolute top-1/2 left-3 h-4 w-4 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={f.search}
          aria-label={f.search}
          className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pr-3 pl-9 text-xs text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
        />
      </div>
      {f.selects.map((s, i) => {
        const dim = dims[i];
        if (!dim) return null;
        return (
          <FilterDropdown
            key={s.label}
            label={s.label}
            value={filters[dim]}
            options={[{ value: "all", label: s.value }, ...options[dim]]}
            onSelect={(v) => setFilters({ ...filters, [dim]: v })}
          />
        );
      })}
      {f.views.map((v, i) => {
        const preset = VIEW_PRESETS[i];
        if (!preset) return null;
        const on = sameFilters(filters, preset);
        return (
          <button
            key={v}
            type="button"
            aria-pressed={on}
            onClick={() => setFilters(preset)}
            className={cn(
              "flex h-9 items-center gap-1.5 rounded-md border px-2.5 text-[0.7rem]",
              on
                ? "border-[#7c5cf5]/60 bg-[#4c3fb0]/25 text-[#c4b5fd]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            <Eye className="h-3.5 w-3.5" /> {v}
          </button>
        );
      })}
      {touched ? (
        <ResetButton
          onClick={() => {
            setFilters(ALL_FILTERS);
            setSearch("");
          }}
        />
      ) : null}
      <span className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)]">
        <Layers className="h-3.5 w-3.5" /> {count}
      </span>
    </section>
  );
}

function TaskTable({
  t,
  data,
  tasks,
  selected,
  onSelect,
}: {
  t: T;
  data: Data;
  tasks: TaskT[];
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const tbl = data.table;
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    if (sortCol === null) return tasks;
    const get = SORT_VALUE[sortCol];
    if (!get) return tasks;
    return [...tasks].sort((a, b) => {
      const va = get(a);
      const vb = get(b);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [tasks, sortCol, sortDir]);

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

  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="flex items-center gap-1 border-b border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] font-medium text-[var(--tessera-text)]">
        <span>{tbl.count}</span>
        <ExplainInfo k="table" title={tbl.count} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] table-fixed border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => {
                const sortable = Boolean(SORT_VALUE[i]);
                return (
                  <th
                    key={c}
                    style={{ width: COL_W[i] }}
                    aria-sort={
                      sortCol === i ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                    }
                    className={cn("py-1.5 font-medium", i === 0 ? "pl-5 pr-2" : "px-2")}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(i)}
                        className={cn(
                          "inline-flex items-center gap-1 uppercase tracking-wide hover:text-[var(--tessera-text)]",
                          sortCol === i && "text-[var(--tessera-text)]",
                        )}
                      >
                        {c}
                        {sortCol === i ? (
                          <span className="text-[0.7rem]">{sortDir === "asc" ? "▲" : "▼"}</span>
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      c
                    )}
                  </th>
                );
              })}
              <th className="w-28 px-2 py-1.5" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {pageRows.map((it) => {
              const active = it.key === selected;
              return (
                <tr
                  key={it.key ?? `${it.title}-${it.ref}`}
                  // biome-ignore lint/a11y/useSemanticElements: a data row selects the item and stays keyboard reachable
                  role="button"
                  tabIndex={0}
                  aria-label={it.title}
                  aria-pressed={active}
                  onClick={() => it.key && onSelect(it.key)}
                  onKeyDown={(e) => {
                    if ((e.key === "Enter" || e.key === " ") && it.key) {
                      e.preventDefault();
                      onSelect(it.key);
                    }
                  }}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors last:border-0 hover:bg-[#1c1740] focus-visible:bg-[#1c1740]",
                    active && "bg-[#241b4d] shadow-[inset_3px_0_0_#7c5cf5]",
                  )}
                >
                  <td className="py-2 pl-5 pr-2">
                    <Badge className={PRIO_TONE[it.prio_tone] ?? PRIO_TONE.mod}>
                      {it.priority}
                    </Badge>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text-muted)]">
                    <Truncate full={it.type}>{it.type}</Truncate>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text)]">
                    <Truncate full={it.title}>{it.title}</Truncate>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text-muted)]">
                    <Truncate full={`${it.source} ${it.ref}`}>
                      {it.source} <span className="font-mono text-[0.58rem]">{it.ref}</span>
                    </Truncate>
                  </td>
                  <td className="px-2 py-2 text-[var(--tessera-text)]">
                    <Truncate full={it.assignee}>{it.assignee}</Truncate>
                  </td>
                  <td
                    className={cn(
                      "px-2 py-2 font-medium tabular-nums",
                      SLA_TONE[it.sla_tone] ?? "",
                    )}
                  >
                    {it.sla}
                  </td>
                  <td className="px-2 py-2 font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">
                    {it.due}
                  </td>
                  <td className="px-2 py-2">
                    <Badge className={STATUS_TONE[it.status_tone] ?? STATUS_TONE.todo}>
                      {it.status}
                    </Badge>
                  </td>
                  <td className="px-2 py-2">
                    <span className="flex items-center justify-end gap-1 whitespace-nowrap">
                      <span className="text-[0.66rem] text-[#b9a6ff] opacity-0 transition-opacity group-hover:opacity-100">
                        {t("rowOpen")}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#b9a6ff]" />
                    </span>
                  </td>
                </tr>
              );
            })}
            {total === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length + 1}
                  className="px-2 py-6 text-center text-[0.7rem] text-[var(--tessera-text-muted)]"
                >
                  {t("empty")}
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
                ? "border-[#b9a6ff]/60 bg-[#b9a6ff]/15 font-medium text-white"
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

function TaskDrawer({
  t,
  data,
  detail,
  busy,
  onClose,
  onTake,
  onResolve,
  onAssign,
}: {
  t: T;
  data: Data;
  detail: DetailT;
  busy: boolean;
  onClose: () => void;
  onTake: () => void;
  onResolve: () => void;
  onAssign: () => void;
}) {
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  const [shown, setShown] = useState(false);
  const [tab, setTab] = useState(0);
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

  const d = detail;
  const s = data.status;
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
        aria-label={d.title}
        onKeyDown={onTrapKey}
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        className={cn(
          "static m-0 block h-full w-full max-w-[440px] bg-transparent p-0 transition-transform duration-200 ease-out",
          shown ? "translate-x-0" : "translate-x-full",
        )}
      >
        <aside className="flex h-full w-full min-w-0 flex-col gap-3 overflow-y-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]">
          {/* header */}
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Badge className={PRIO_TONE[d.selected.prio_tone] ?? PRIO_TONE.crit}>
                  {d.selected.priority}
                </Badge>
                <span className="font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                  {d.selected.id}
                </span>
              </div>
              <p className="mt-1.5 pr-6 text-[0.92rem] font-semibold leading-tight">
                {d.selected.title}
              </p>
              <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">
                {d.selected.subtitle}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("close")}
              className="shrink-0 rounded-md border border-[var(--tessera-border)] p-1 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* contexte */}
          <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
            <nav className="mb-2 flex items-center gap-4 border-b border-[var(--tessera-border)]">
              {d.tabs.map((tb, i) => (
                <button
                  key={tb}
                  type="button"
                  aria-pressed={i === tab}
                  onClick={() => setTab(i)}
                  className={cn(
                    "-mb-px border-b-2 py-1.5 text-[0.66rem] transition-colors",
                    i === tab
                      ? "border-emerald-400 font-medium text-[var(--tessera-text)]"
                      : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
                  )}
                >
                  {tb}
                </button>
              ))}
            </nav>
            {tab === 0 ? (
              <>
                <dl className="flex flex-col gap-1.5 text-[0.7rem]">
                  {d.context.map((c) => (
                    <div key={c.label} className="flex items-center justify-between gap-2">
                      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{c.label}</dt>
                      <Truncate
                        as="dd"
                        full={c.value}
                        className="min-w-0 text-right font-medium text-[var(--tessera-text)]"
                      >
                        {c.value}
                      </Truncate>
                    </div>
                  ))}
                </dl>
                <p className="mt-2 text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                  {d.summary_label}
                </p>
                <p className="text-[0.7rem] leading-snug text-[var(--tessera-text)]">{d.summary}</p>
              </>
            ) : null}
            {tab === 1 ? (
              <>
                <dl className="flex flex-col gap-1.5 text-[0.7rem]">
                  {d.sla_rows.map((r) => (
                    <div key={r.label} className="flex items-center justify-between gap-2">
                      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{r.label}</dt>
                      <Truncate
                        as="dd"
                        full={r.value}
                        className="min-w-0 text-right font-medium text-[var(--tessera-text)]"
                      >
                        {r.value}
                      </Truncate>
                    </div>
                  ))}
                </dl>
                <p className="mt-2 text-[0.62rem] leading-snug text-[var(--tessera-text-muted)]">
                  {t("historyNote")}
                </p>
              </>
            ) : null}
            {tab === 2 ? (
              <>
                <dl className="flex flex-col gap-1.5 text-[0.7rem]">
                  {d.context.slice(0, 1).map((c) => (
                    <div key={c.label} className="flex items-center justify-between gap-2">
                      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{c.label}</dt>
                      <Truncate
                        as="dd"
                        full={c.value}
                        className="min-w-0 text-right font-medium text-[var(--tessera-text)]"
                      >
                        {c.value}
                      </Truncate>
                    </div>
                  ))}
                </dl>
                <Link
                  href="/surveiller/qualite-ia"
                  className="mt-2 inline-flex items-center gap-1 text-[0.68rem] text-[#87bfff] hover:text-[#a9d2ff]"
                >
                  {d.selected.cta} <ArrowUpRight className="h-3 w-3" />
                </Link>
              </>
            ) : null}
            {tab === 3 ? (
              <p className="py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
                {t("noRelations")}
              </p>
            ) : null}
          </div>

          {/* echeance & sla */}
          <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
            <h4 className="mb-1.5 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.sla_title}
            </h4>
            <p
              className={cn(
                "text-[1.1rem] font-semibold tabular-nums",
                SLA_TONE[d.sla_tone] ?? "text-[var(--tessera-text)]",
              )}
            >
              {d.sla_value}
            </p>
            <p
              className={cn(
                "mb-2 text-[0.58rem]",
                SLA_TONE[d.sla_tone] ?? "text-[var(--tessera-text-muted)]",
              )}
            >
              {d.sla_note}
            </p>
            <dl className="flex flex-col gap-1.5 text-[0.7rem]">
              {d.sla_rows.map((r) => (
                <div key={r.label} className="flex items-center justify-between gap-2">
                  <dt className="text-[var(--tessera-text-muted)]">{r.label}</dt>
                  <dd className="tabular-nums text-[var(--tessera-text)]">{r.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* assignation */}
          <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
            <h4 className="mb-1.5 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.assign_title}
            </h4>
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{d.assign_label}</p>
                <span className="mt-0.5 inline-flex items-center gap-1.5 text-[0.72rem] text-[var(--tessera-text)]">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#6d4aed]/20 text-[0.5rem] font-medium text-[#b9a6ff]">
                    {d.assignee
                      .split(" ")
                      .map((p) => p[0] ?? "")
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </span>
                  {d.assignee}
                </span>
              </div>
              <div className="text-right">
                <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{d.team_label}</p>
                <p className="text-[0.7rem] text-[var(--tessera-text)]">{d.team}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={onAssign}
              disabled={busy}
              className="mt-2 flex w-full items-center justify-center gap-1 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/40 px-2.5 py-1.5 text-[0.68rem] text-[#c4b5fd] hover:bg-[#4c3fb0]/60 disabled:opacity-50"
            >
              <UserPlus className="h-3.5 w-3.5" /> {d.reassign}
            </button>
          </div>

          {/* statut & actions */}
          {s ? (
            <div className="mt-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
              <h4 className="mb-1.5 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
                {s.title}
              </h4>
              <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.label}</p>
              <span className="mt-0.5 flex h-8 w-full items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2.5 text-[0.68rem] text-[var(--tessera-text)]">
                {d.current_status ?? s.value}
              </span>
              <div className="mt-2 flex flex-col gap-1.5">
                <button
                  type="button"
                  onClick={onTake}
                  disabled={busy}
                  className="flex h-9 items-center justify-center rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-[0.7rem] font-medium text-white hover:bg-[#7c5cf5] disabled:opacity-50"
                >
                  {s.primary}
                </button>
                <button
                  type="button"
                  onClick={onResolve}
                  disabled={busy}
                  className="flex h-8 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
                >
                  {s.secondary}
                </button>
              </div>
            </div>
          ) : null}
        </aside>
      </dialog>
    </div>
  );
}

function Panel({
  title,
  info,
  children,
}: { title: string; info?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex min-w-0 items-center gap-1 text-[0.74rem] font-semibold text-[var(--tessera-text)]">
          <Truncate full={title} className="min-w-0">
            {title}
          </Truncate>
          {info}
        </h3>
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

function Donut({ data }: { data: Data }) {
  const d = data.donut;
  if (!d) return null;
  const sum = d.segments.reduce((s, x) => s + x.count, 0) || 1;
  const R = 41;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <Panel title={d.title} info={<ExplainInfo k="donut" title={d.title} />}>
      <div className="flex items-center gap-3">
        <div className="relative h-[112px] w-[112px] shrink-0">
          <svg viewBox="0 0 112 112" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle cx="56" cy="56" r={R} fill="none" stroke="var(--tessera-bg)" strokeWidth="9" />
            {d.segments.map((s) => {
              const frac = s.count / sum;
              const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
              off += frac;
              return (
                <circle
                  key={s.label}
                  cx="56"
                  cy="56"
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
          <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
            <span className="max-w-[54px] truncate text-base font-semibold leading-none tabular-nums text-white">
              {d.center}
            </span>
            <Truncate
              lines={2}
              className="max-w-[54px] break-words text-center text-[0.46rem] uppercase leading-tight text-[var(--tessera-text-muted)]"
            >
              {d.center_label}
            </Truncate>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.62rem]">
          {d.segments.map((s) => (
            <li key={s.label} className="flex flex-col gap-0.5">
              <span className="flex min-w-0 items-center gap-1">
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: s.color }}
                />
                <Truncate full={s.label} className="min-w-0 text-[var(--tessera-text)]">
                  {s.label}
                </Truncate>
              </span>
              <span className="pl-2.5 tabular-nums text-[var(--tessera-text-muted)]">
                {s.count} ({s.share})
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function Sla({ data }: { data: Data }) {
  const s = data.sla;
  if (!s) return null;
  const max = Math.max(...s.buckets.map((b) => b.count), 1);
  return (
    <Panel title={s.title} info={<ExplainInfo k="sla" title={s.title} />}>
      <ul className="flex flex-col gap-2">
        {s.buckets.map((b) => (
          <li key={b.label} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-16 shrink-0 text-[var(--tessera-text)]">{b.label}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
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

function Quick({ t, data }: { t: T; data: Data }) {
  const q = data.quick;
  const tbl = data.table;
  if (!q) return null;
  const icons: LucideIcon[] = [
    ArrowUpRight,
    UserPlus,
    StickyNote,
    CheckCircle2,
    PlusCircle,
    FileSignature,
  ];
  const exportCsv = () => {
    if (!tbl) return;
    downloadBlob(
      "tessera-a-faire.csv",
      "text/csv",
      toCsv(
        tbl.columns,
        tbl.tasks.map((it) => [
          it.priority,
          it.type,
          it.title,
          `${it.source} ${it.ref}`,
          it.assignee,
          it.sla,
          it.due,
          it.status,
        ]),
      ),
    );
  };
  const btnCls =
    "flex w-full flex-col items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-2 text-center text-[0.6rem] text-[var(--tessera-text)]";
  return (
    <Panel title={q.title} info={<ExplainInfo k="quick" title={q.title} />}>
      <div className="grid grid-cols-3 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? ArrowUpRight;
          const inner = (
            <>
              <Icon className="h-4 w-4 text-[#b9a6ff]" />
              <Truncate full={it} className="min-w-0">
                {it}
              </Truncate>
            </>
          );
          if (i === 4) {
            return (
              <Link
                key={it}
                href="/surveiller/qualite-ia"
                className={cn(btnCls, "hover:border-[#7c5cf5]/50")}
              >
                {inner}
              </Link>
            );
          }
          if (i === 5) {
            return (
              <button
                key={it}
                type="button"
                onClick={exportCsv}
                className={cn(btnCls, "hover:border-[#7c5cf5]/50")}
              >
                {inner}
              </button>
            );
          }
          return (
            <span key={it} title={t("quickNeedsRow")}>
              <button
                type="button"
                disabled
                className={cn(btnCls, "cursor-not-allowed opacity-50")}
              >
                {inner}
              </button>
            </span>
          );
        })}
      </div>
    </Panel>
  );
}

function Activity({ data }: { data: Data }) {
  const a = data.activity;
  if (!a) return null;
  return (
    <Panel title={a.title} info={<ExplainInfo k="activity" title={a.title} />}>
      <ul className="flex flex-col gap-1.5">
        {a.items.map((it, i) => (
          <li
            key={`${it.time}-${it.action}-${i}`}
            className="flex items-center gap-2 text-[0.64rem]"
          >
            <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-400" />
            <span className="shrink-0 font-medium text-[var(--tessera-text)]">{it.actor}</span>
            <Truncate full={it.action} className="min-w-0 flex-1 text-[var(--tessera-text-muted)]">
              {it.action}
            </Truncate>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {it.time}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
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

function Footer({ data }: { data: Data }) {
  const f = data.footer;
  if (!f) return null;
  return (
    <footer className="mt-1 flex flex-wrap items-center gap-x-3 border-t border-[var(--tessera-border)] pt-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
      <span>{f.check}</span>
      <span className="inline-flex items-center gap-1 text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" /> {f.status}
      </span>
    </footer>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Clock,
  Coins,
  Download,
  GitCompare,
  type LucideIcon,
  MessagesSquare,
  Play,
  Search,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import type { Route } from "next";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchAgentHistorique } from "@/lib/api/client";
import type { AgentHistorique as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import { AgentCrossLinks } from "./agent-cross-links";
import { AgentSubtabs } from "./agent-subtabs";

type RowT = NonNullable<Data["table"]>["rows"][number];

const KPI_ICONS: LucideIcon[] = [MessagesSquare, MessagesSquare, Sparkles, Target, Clock, Coins];
const SPARK_TONE: Record<string, string> = {
  violet: "#8b7cf0",
  blue: "#4c8bf5",
  green: "#34d399",
  amber: "#e0a23a",
};
const TONE_TEXT: Record<string, string> = {
  good: "text-emerald-400",
  bad: "text-red-400",
  muted: "text-[var(--tessera-text-muted)]",
};
const SCORE_TEXT: Record<string, string> = {
  good: "text-emerald-300",
  warn: "text-amber-300",
  crit: "text-red-300",
};
const STATUS_BADGE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  info: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  warn: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  bad: "border-red-500/30 bg-red-500/15 text-red-300",
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
};
const SEG_FILL: Record<string, string> = {
  green: "#34d399",
  blue: "#4c8bf5",
  amber: "#e0a23a",
  red: "#f87171",
};
const SEG_DOT: Record<string, string> = {
  green: "bg-emerald-400",
  blue: "bg-sky-400",
  amber: "bg-amber-400",
  red: "bg-red-400",
};
const WATCH_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  crit: "bg-red-400",
};
const PER_PAGE_OPTS = [10, 25, 50, 100];
const MAX_PAGE_BUTTONS = 5;
// Sort accessors keyed by column index (i18n-stable, never on the display string).
const NUMERIC_COLS = new Set([4, 5, 7, 8]);

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

function rowSortKey(r: RowT, col: number): string | number {
  switch (col) {
    case 0:
      return r.sid;
    case 1:
      return r.user;
    case 2:
      return r.agent;
    case 3:
      return r.start_ts;
    case 4:
      return Number(r.messages);
    case 5:
      return r.score_num;
    case 6:
      return r.status;
    case 7:
      return r.latency_ms;
    case 8:
      return r.tokens_num;
    default:
      return r.sid;
  }
}

function compareRows(a: RowT, b: RowT, col: number, dir: "asc" | "desc"): number {
  const av = rowSortKey(a, col);
  const bv = rowSortKey(b, col);
  let cmp: number;
  if (NUMERIC_COLS.has(col)) cmp = Number(av) - Number(bv);
  else cmp = String(av).localeCompare(String(bv), "fr");
  return dir === "asc" ? cmp : -cmp;
}

export function AgentHistorique() {
  const t = useTranslations("agentHistorique");
  const agentId = useAgentId();
  const [subtab, setSubtab] = useState("");
  const { data } = useQuery({
    queryKey: ["agent-historique", agentId],
    queryFn: ({ signal }) => fetchAgentHistorique(agentId, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [search, setSearch] = useState("");
  const [catKey, setCatKey] = useState("all");
  const [langKey, setLangKey] = useState("all");
  const [statusKey, setStatusKey] = useState("all");
  const [scoreKey, setScoreKey] = useState("all");
  const [sortCol, setSortCol] = useState<number | null>(3);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [selected, setSelected] = useState<string | null>(null);

  const allRows = data?.table?.rows ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allRows.filter((r) => {
      if (catKey !== "all" && r.category_key !== catKey) return false;
      if (langKey !== "all" && r.lang !== langKey) return false;
      if (statusKey !== "all" && r.status_tone !== statusKey) return false;
      if (scoreKey === "high" && r.score_num < 5) return false;
      if (scoreKey === "low" && r.score_num >= 5) return false;
      if (q) {
        const hay = `${r.sid} ${r.case_id} ${r.category_label} ${r.question}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [allRows, search, catKey, langKey, statusKey, scoreKey]);

  const sorted = useMemo(() => {
    if (sortCol === null) return filtered;
    return [...filtered].sort((a, b) => compareRows(a, b, sortCol, sortDir));
  }, [filtered, sortCol, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on any filter/sort change
  useEffect(
    () => setPage(1),
    [search, catKey, langKey, statusKey, scoreKey, sortCol, sortDir, perPage],
  );
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * perPage;
  const pageRows = sorted.slice(startIdx, startIdx + perPage);

  const selectedRow = sorted.find((r) => r.sid === selected) ?? pageRows[0] ?? allRows[0] ?? null;

  const resetFilters = useCallback(() => {
    setSearch("");
    setCatKey("all");
    setLangKey("all");
    setStatusKey("all");
    setScoreKey("all");
  }, []);

  const exportCsv = useCallback(() => {
    const head = ["sid", "categorie", "langue", "statut", "score", "latence_ms", "tokens"];
    const lines = sorted.map((r) =>
      [r.sid, r.category_label, r.lang, r.status, r.score, r.latency_ms, r.tokens_num]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(","),
    );
    const blob = new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "tessera-historique-sessions.csv";
    link.click();
    URL.revokeObjectURL(url);
  }, [sorted]);

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  const a = data.actions;
  const subtabs = data.subtabs ?? [];
  const active = subtab || subtabs[0] || "";
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="historique" />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={exportCsv}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <Download className="h-4 w-4" /> {a?.export}
        </button>
        <Link
          href="/prouver/etat-a-date"
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <GitCompare className="h-4 w-4" /> {a?.compare}
        </Link>
        <Link
          href="/prouver/evidence-store"
          className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5]"
        >
          {a?.create}
        </Link>
      </div>

      <AgentSubtabs tabs={subtabs} active={active} onSelect={setSubtab} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Sparkles} />
        ))}
      </div>

      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
          <Filters
            data={data}
            search={search}
            setSearch={setSearch}
            catKey={catKey}
            setCatKey={setCatKey}
            langKey={langKey}
            setLangKey={setLangKey}
            statusKey={statusKey}
            setStatusKey={setStatusKey}
            scoreKey={scoreKey}
            setScoreKey={setScoreKey}
            onReset={resetFilters}
          />
          <SessionsTable
            data={data}
            rows={pageRows}
            total={total}
            selected={selectedRow?.sid ?? null}
            onSelect={setSelected}
            sortCol={sortCol}
            sortDir={sortDir}
            onSort={(col) => {
              if (col === sortCol) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
              else {
                setSortCol(col);
                setSortDir("asc");
              }
            }}
            page={safePage}
            totalPages={totalPages}
            start={total === 0 ? 0 : startIdx + 1}
            end={Math.min(startIdx + perPage, total)}
            perPage={perPage}
            onPage={setPage}
            onPerPage={setPerPage}
          />
          <div className="grid gap-2.5 lg:grid-cols-2 xl:grid-cols-4">
            <TrendCard data={data} />
            <ByAgent data={data} />
            <ScoreDonut data={data} />
            <SuccessCard data={data} />
          </div>
          <div className="grid gap-2.5 md:grid-cols-2">
            <Watch data={data} />
            <Quick data={data} onFailed={() => setStatusKey("bad")} onExport={exportCsv} />
          </div>
        </div>
        <Detail data={data} row={selectedRow} className="xl:col-span-4" />
      </div>
    </div>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[96px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <span className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </span>
      </div>
      <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {kpi.value}
      </p>
      <div className="flex items-end justify-between gap-2">
        <span
          className={cn(
            "text-[0.58rem] tabular-nums",
            TONE_TEXT[kpi.delta_tone] ?? TONE_TEXT.muted,
          )}
        >
          {kpi.delta}
        </span>
        <Spark values={kpi.series} color={SPARK_TONE[kpi.tone] ?? "#8b7cf0"} />
      </div>
    </div>
  );
}

function Spark({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 52;
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
      className="h-4 w-14"
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
          className="absolute right-0 z-20 mt-1 max-h-72 w-52 overflow-y-auto rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
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
              {o.value === value ? <span className="text-[#b9a6ff]">&bull;</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

type FiltersProps = {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  catKey: string;
  setCatKey: (v: string) => void;
  langKey: string;
  setLangKey: (v: string) => void;
  statusKey: string;
  setStatusKey: (v: string) => void;
  scoreKey: string;
  setScoreKey: (v: string) => void;
  onReset: () => void;
};

function Filters(p: FiltersProps) {
  const f = p.data.filters;
  if (!f) return null;
  const opt = (
    items: { key: string; label: string }[],
    allLabel: string,
  ): { value: string; label: string }[] => [
    { value: "all", label: allLabel },
    ...items.map((i) => ({ value: i.key, label: i.label })),
  ];
  const anyActive =
    p.search !== "" ||
    p.catKey !== "all" ||
    p.langKey !== "all" ||
    p.statusKey !== "all" ||
    p.scoreKey !== "all";
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[220px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <input
          value={p.search}
          onChange={(e) => p.setSearch(e.target.value)}
          placeholder={f.search}
          aria-label={f.search}
          className="h-full min-w-0 flex-1 bg-transparent text-[0.74rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
        />
      </div>
      <FilterDropdown
        label="Catégorie"
        value={p.catKey}
        options={opt(f.options.category, "Toutes")}
        onSelect={p.setCatKey}
      />
      <FilterDropdown
        label="Langue"
        value={p.langKey}
        options={opt(f.options.lang, "Toutes")}
        onSelect={p.setLangKey}
      />
      <FilterDropdown
        label="Statut"
        value={p.statusKey}
        options={opt(f.options.status, "Tous")}
        onSelect={p.setStatusKey}
      />
      <FilterDropdown
        label="Score"
        value={p.scoreKey}
        options={opt(f.options.score, "Tous")}
        onSelect={p.setScoreKey}
      />
      {anyActive ? (
        <button
          type="button"
          onClick={p.onReset}
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-3.5 w-3.5" /> Réinitialiser
        </button>
      ) : null}
    </div>
  );
}

type TableProps = {
  data: Data;
  rows: RowT[];
  total: number;
  selected: string | null;
  onSelect: (sid: string) => void;
  sortCol: number | null;
  sortDir: "asc" | "desc";
  onSort: (col: number) => void;
  page: number;
  totalPages: number;
  start: number;
  end: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
};

function SessionsTable(p: TableProps) {
  const tbl = p.data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[840px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => (
                <th
                  key={c}
                  aria-sort={
                    p.sortCol === i ? (p.sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className={cn("px-3 py-2 font-medium", i === 0 ? "" : "whitespace-nowrap")}
                >
                  <button
                    type="button"
                    onClick={() => p.onSort(i)}
                    className={cn(
                      "inline-flex items-center gap-1 hover:text-[var(--tessera-text)]",
                      p.sortCol === i ? "text-[var(--tessera-text)]" : "",
                    )}
                  >
                    {c}
                    {p.sortCol === i ? (
                      <ChevronDown className={cn("h-3 w-3", p.sortDir === "asc" && "rotate-180")} />
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.rows.map((r) => {
              const on = r.sid === p.selected;
              return (
                <tr
                  key={r.sid}
                  // biome-ignore lint/a11y/useSemanticElements: a table row is the click target here
                  role="button"
                  tabIndex={0}
                  aria-label={`Session ${r.sid}`}
                  onClick={() => p.onSelect(r.sid)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      p.onSelect(r.sid);
                    }
                  }}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 last:border-0 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#8b7cf0]",
                    on ? "bg-[#6d4aed]/10" : "hover:bg-[var(--tessera-bg)]/40",
                  )}
                >
                  <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[0.66rem] text-[#b9a6ff]">
                    {r.sid}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <span className="inline-flex items-center gap-1.5 text-[0.7rem] text-[var(--tessera-text)]">
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#6d4aed]/20 text-[0.52rem] font-medium text-[#b9a6ff]">
                        {initials(r.user)}
                      </span>
                      {r.user}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
                    {r.agent}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {r.start}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text)]">
                    {r.messages}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5">
                    <span
                      className={cn(
                        "text-[0.7rem] font-medium tabular-nums",
                        SCORE_TEXT[r.score_tone] ?? "",
                      )}
                    >
                      {r.score}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                        STATUS_BADGE[r.status_tone] ?? STATUS_BADGE.good,
                      )}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {r.latency}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {r.tokens}
                  </td>
                </tr>
              );
            })}
            {p.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length}
                  className="px-3 py-8 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  Aucune session ne correspond aux filtres.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pagination
        page={p.page}
        totalPages={p.totalPages}
        start={p.start}
        end={p.end}
        total={p.total}
        perPage={p.perPage}
        onPage={p.onPage}
        onPerPage={p.onPerPage}
      />
    </section>
  );
}

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(MAX_PAGE_BUTTONS, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, totalPages - span + 1);
  return Array.from({ length: span }, (_, i) => first + i);
}

function Pagination({
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
}: {
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
        {start}-{end} sur {total} sessions
      </span>
      <div className="flex items-center gap-1">
        <PageArrow dir="prev" disabled={page <= 1} onClick={() => onPage(Math.max(1, page - 1))} />
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
        <PageArrow
          dir="next"
          disabled={page >= totalPages}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
        />
      </div>
      <label className="flex items-center gap-2">
        <span>Lignes par page</span>
        <select
          value={perPage}
          onChange={(e) => onPerPage(Number(e.target.value))}
          className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.72rem] text-[var(--tessera-text)] focus:outline-none"
        >
          {PER_PAGE_OPTS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function PageArrow({
  dir,
  disabled,
  onClick,
}: {
  dir: "prev" | "next";
  disabled: boolean;
  onClick: () => void;
}) {
  const Icon = dir === "prev" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={dir === "prev" ? "Page précédente" : "Page suivante"}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] enabled:hover:text-[var(--tessera-text)] disabled:opacity-40"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function PanelCard({
  title,
  control,
  cta,
  ctaHref,
  children,
}: {
  title: string;
  control?: string;
  cta?: string;
  ctaHref?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-[0.72rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
        {control ? (
          <span className="inline-flex items-center gap-1 rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[0.6rem] text-[var(--tessera-text-muted)]">
            {control}
          </span>
        ) : null}
      </div>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta && ctaHref ? (
        <Link
          href={ctaHref as Route}
          className="mt-2.5 flex items-center gap-1 self-start text-[0.64rem] text-[#b9a6ff] hover:text-white"
        >
          {cta} <ChevronRight className="h-3 w-3" />
        </Link>
      ) : null}
    </section>
  );
}

function TrendCard({ data }: { data: Data }) {
  const tr = data.trend;
  if (!tr) return null;
  return (
    <PanelCard title={tr.title} control={tr.control}>
      <LineChart a={tr.series} b={tr.prev} />
      <div className="mt-2 flex flex-wrap items-center gap-3 text-[0.6rem] text-[var(--tessera-text-muted)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-[#8b7cf0]" /> {tr.legend}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-slate-500" /> {tr.legend_prev}
        </span>
      </div>
    </PanelCard>
  );
}

function LineChart({ a, b }: { a: number[]; b: number[] }) {
  const all = [...a, ...b];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const W = 100;
  const H = 46;
  const path = (vals: number[]) =>
    vals
      .map((v, i) => {
        const x = (i / (vals.length - 1)) * W;
        const y = H - ((v - min) / span) * (H - 4) - 2;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-16 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d={path(b)}
        fill="none"
        stroke="#64748b"
        strokeWidth="1.2"
        strokeDasharray="3 2"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={path(a)}
        fill="none"
        stroke="#8b7cf0"
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function ByAgent({ data }: { data: Data }) {
  const b = data.by_agent;
  if (!b) return null;
  return (
    <PanelCard title={b.title} cta={b.cta} ctaHref={b.cta_href}>
      <ul className="flex flex-col gap-2">
        {b.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2 text-[0.66rem]">
              <span className="min-w-0 truncate text-[var(--tessera-text)]">{it.label}</span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {it.value} <span className="text-[0.58rem]">({it.share})</span>
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
              <div className="h-full rounded-full bg-[#8b7cf0]" style={{ width: `${it.pct}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function ScoreDonut({ data }: { data: Data }) {
  const s = data.scores;
  if (!s) return null;
  let acc = 0;
  return (
    <PanelCard title={s.title}>
      <div className="flex items-center gap-3">
        <span className="relative inline-flex h-[68px] w-[68px] shrink-0 items-center justify-center">
          <svg viewBox="0 0 36 36" className="h-[68px] w-[68px] -rotate-90" aria-hidden="true">
            <circle
              cx="18"
              cy="18"
              r="15.915"
              fill="none"
              stroke="var(--tessera-bg)"
              strokeWidth="3.4"
            />
            {s.segments.map((seg) => {
              const dash = `${seg.pct} ${100 - seg.pct}`;
              const off = -acc;
              acc += seg.pct;
              return (
                <circle
                  key={seg.label}
                  cx="18"
                  cy="18"
                  r="15.915"
                  fill="none"
                  stroke={SEG_FILL[seg.tone] ?? "#64748b"}
                  strokeWidth="3.4"
                  strokeDasharray={dash}
                  strokeDashoffset={off}
                />
              );
            })}
          </svg>
          <span className="absolute flex flex-col items-center">
            <span className="text-[0.7rem] font-semibold tabular-nums text-[var(--tessera-text)]">
              {s.center}
            </span>
            <span className="text-[0.5rem] text-[var(--tessera-text-muted)]">{s.center_label}</span>
          </span>
        </span>
        <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.62rem]">
          {s.segments.map((seg) => (
            <li key={seg.label} className="flex items-center justify-between gap-1.5">
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    SEG_DOT[seg.tone] ?? "bg-slate-400",
                  )}
                />
                <span className="truncate text-[var(--tessera-text-muted)]">{seg.label}</span>
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text)]">
                {seg.value} <span className="text-[var(--tessera-text-muted)]">({seg.share})</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </PanelCard>
  );
}

function SuccessCard({ data }: { data: Data }) {
  const s = data.success;
  if (!s) return null;
  const r = 15.915;
  const off = 100 - s.gauge;
  return (
    <PanelCard title={s.title} cta={s.cta} ctaHref={s.cta_href}>
      <div className="flex flex-1 flex-col items-center justify-center gap-1">
        <span className="relative inline-flex h-[80px] w-[80px] items-center justify-center">
          <svg viewBox="0 0 36 36" className="h-[80px] w-[80px] -rotate-90" aria-hidden="true">
            <circle
              cx="18"
              cy="18"
              r={r}
              fill="none"
              stroke="var(--tessera-bg)"
              strokeWidth="3.4"
            />
            <circle
              cx="18"
              cy="18"
              r={r}
              fill="none"
              stroke="#34d399"
              strokeWidth="3.4"
              strokeLinecap="round"
              strokeDasharray={`${s.gauge} ${off}`}
            />
          </svg>
          <span className="absolute text-[0.95rem] font-semibold tabular-nums text-[var(--tessera-text)]">
            {s.value}
          </span>
        </span>
        <span className="text-[0.66rem] text-emerald-300">{s.note}</span>
      </div>
    </PanelCard>
  );
}

function Watch({ data }: { data: Data }) {
  const w = data.watch;
  if (!w) return null;
  return (
    <PanelCard title={w.title} cta={w.cta} ctaHref={w.cta_href}>
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
              <span className="block truncate text-[0.72rem] text-[var(--tessera-text)]">
                {it.title}
              </span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {it.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function Quick({
  data,
  onFailed,
  onExport,
}: {
  data: Data;
  onFailed: () => void;
  onExport: () => void;
}) {
  const q = data.quick;
  const agentId = useAgentId();
  if (!q) return null;
  const icons = [BarChart3, Target, Download, Play];
  const cls =
    "flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.68rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50";
  const HREF: Record<string, string> = {
    scores: agentPath(agentId, "evaluations"),
    evaluate: agentPath(agentId, "console"),
  };
  return (
    <PanelCard title={q.title}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? Play;
          const inner = (
            <>
              <Icon className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
              <span className="min-w-0 truncate">{it.label}</span>
            </>
          );
          const href = HREF[it.key];
          if (href) {
            return (
              <Link key={it.key} href={href as Route} className={cls}>
                {inner}
              </Link>
            );
          }
          return (
            <button
              key={it.key}
              type="button"
              onClick={it.key === "export" ? onExport : onFailed}
              className={cls}
            >
              {inner}
            </button>
          );
        })}
      </div>
    </PanelCard>
  );
}

function Detail({
  data,
  row,
  className,
}: {
  data: Data;
  row: RowT | null;
  className?: string;
}) {
  const agentId = useAgentId();
  const labels = data.detail_labels;
  const meta = data.meta;
  const tabs = labels?.tabs ?? ["Resume", "Messages (2)", "Evaluation", "Activite"];
  const [tab, setTab] = useState(tabs[0] ?? "Resume");
  if (!labels || !meta || !row) return null;

  const fields: { label: string; value: string; tone?: string }[] = [
    { label: "Utilisateur", value: row.user },
    { label: "Agent", value: row.agent },
    { label: "Durée totale", value: row.latency },
    { label: "Messages", value: row.messages },
    { label: "Score", value: `${row.score} / 10`, tone: row.score_tone },
    { label: "Statut", value: row.status, tone: row.status_tone },
    { label: "Temps de réponse (p50)", value: row.latency },
    { label: "Tokens", value: row.tokens },
    { label: "Modèle", value: meta.model },
    { label: "Catégorie", value: row.category_label },
  ];
  const evals: { label: string; value: string; scale: string; lead: boolean }[] = [
    { label: "Score global", value: String(row.score_num), scale: "/10", lead: true },
    { label: "Réussite", value: row.passed ? "Oui" : "Non", scale: "", lead: false },
    { label: "Escalade requise", value: row.escalation ? "Oui" : "Non", scale: "", lead: false },
    { label: "Outils invoqués", value: String(row.tools_count), scale: "", lead: false },
    {
      label: "Tokens (entrée / sortie)",
      value: `${row.input_tokens} / ${row.output_tokens}`,
      scale: "",
      lead: false,
    },
  ];
  const info: { label: string; value: string }[] = [
    { label: "Session ID", value: row.sid },
    { label: "Cas", value: row.case_id },
    { label: "Catégorie", value: row.category_key },
    { label: "Langue", value: row.lang },
    { label: "Modèle", value: meta.model },
    { label: "Version catalogue", value: meta.catalogue_version },
  ];
  const activity: { time: string; label: string }[] = [
    { time: row.start, label: "Question reçue" },
    { time: row.start, label: "Réponse générée" },
    { time: row.start, label: row.passed ? "Évaluation réussie" : "Évaluation en échec" },
  ];

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-3">
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {labels.eyebrow}
        </p>
        <div className="mt-1 flex items-center gap-2">
          <MessagesSquare className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
          <span className="truncate font-mono text-[0.82rem] font-semibold text-[var(--tessera-text)]">
            {row.sid}
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {tabs.map((tb) => {
          const on = tb === tab;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(tb)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.7rem] transition-colors",
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
        {tab === tabs[0] ? (
          <>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {fields.map((f) => (
                <li key={f.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
                  <span
                    className={cn(
                      "font-medium tabular-nums",
                      f.tone === "good"
                        ? "text-emerald-300"
                        : f.tone === "bad"
                          ? "text-red-300"
                          : "text-[var(--tessera-text)]",
                    )}
                  >
                    {f.value}
                  </span>
                </li>
              ))}
            </ul>

            <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
              <h3 className="mb-1.5 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                {labels.config_title}
              </h3>
              <div className="flex items-center justify-between gap-2 text-[0.72rem]">
                <span className="text-[var(--tessera-text)]">{row.agent}</span>
                <span className="rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]">
                  {meta.catalogue_version}
                </span>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                {labels.info_title}
              </h3>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {info.map((it) => (
                  <li key={it.label} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{it.label}</span>
                    <span className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
                      {it.value}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}

        {tab === tabs[1] ? (
          <div className="flex flex-col gap-3">
            <h3 className="text-[0.7rem] font-semibold text-[var(--tessera-text)]">
              {labels.messages_title}
            </h3>
            <div className="flex flex-col items-end gap-1">
              <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">
                {labels.question_label}
              </span>
              <p className="max-w-[92%] rounded-xl rounded-tr-sm border border-cyan-400/25 bg-cyan-400/[0.08] px-3 py-2 text-[0.74rem] leading-relaxed text-[var(--tessera-text)]">
                {row.question}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">
                {labels.response_label}
              </span>
              <p className="rounded-xl rounded-tl-sm border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2 text-[0.74rem] leading-relaxed text-[var(--tessera-text)]">
                {row.response}
              </p>
            </div>
          </div>
        ) : null}

        {tab === tabs[2] ? (
          <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
            <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
              {labels.eval_title}
            </h3>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {evals.map((e) => (
                <li key={e.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{e.label}</span>
                  <span className="tabular-nums">
                    <span
                      className={cn(
                        "font-semibold",
                        e.lead ? "text-[1rem] text-emerald-300" : "text-[var(--tessera-text)]",
                      )}
                    >
                      {e.value}
                    </span>
                    <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">
                      {e.scale}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <Link
              href={agentPath(agentId, "evaluations") as Route}
              className="mt-2 flex items-center gap-1 self-start text-[0.64rem] text-[#b9a6ff] hover:text-white"
            >
              {labels.eval_cta} <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        ) : null}

        {tab === tabs[3] ? (
          <div>
            <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
              {labels.activity_title}
            </h3>
            <ul className="flex flex-col gap-2 text-[0.72rem]">
              {activity.map((it) => (
                <li key={it.label} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                  <span className="text-[var(--tessera-text)]">{it.label}</span>
                  <span className="ml-auto shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                    {it.time}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

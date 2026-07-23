"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Boxes,
  Brain,
  CalendarClock,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Clock,
  Database,
  Download,
  GitBranch,
  History,
  Layers,
  type LucideIcon,
  MessagesSquare,
  Package,
  Scale,
  Search,
  ShieldCheck,
  SortAsc,
  SortDesc,
  Sparkles,
  Tag,
  Users,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { TabStrip } from "@/components/cockpit/tab-strip";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchSourcesOverview } from "@/lib/api/client";
import type { SourcesOverview as SourcesData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const CLASS_BADGE: Record<string, string> = {
  public: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  internal: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  confidential: "border-violet-500/30 bg-violet-500/15 text-violet-300",
};
const STATUS: Record<"active" | "disabled", { dot: string; text: string }> = {
  active: { dot: "bg-emerald-400", text: "text-emerald-300" },
  disabled: { dot: "bg-[var(--tessera-text-muted)]", text: "text-[var(--tessera-text-muted)]" },
};
// Source-type icon: regulation (law), product (package), memory (brain), transcript (chat).
const TYPE_ICON: Record<string, LucideIcon> = {
  regulation: Scale,
  product: Package,
  memory: Brain,
  transcript: MessagesSquare,
};
// Per-type icon colour so the source kind reads at a glance.
const TYPE_ICON_TONE: Record<string, string> = {
  regulation: "text-amber-300",
  product: "text-[#87bfff]",
  memory: "text-fuchsia-300",
  transcript: "text-emerald-300",
};
const ASOF_HREF = "/prouver/etat-a-date";
const REVALIDATE_HREF = "/agir/release-control";
const VERDICT_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  crit: "bg-red-400",
  bad: "bg-amber-400",
  muted: "bg-[var(--tessera-text-muted)]",
};
// The normative's 9-tab strip; each is a real lens over the same live payload.
const VIEWS = [
  "overview",
  "sources",
  "memory",
  "indexation",
  "quality",
  "access",
  "retention",
  "lineage",
  "history",
] as const;
const VIEW_ICONS: Record<(typeof VIEWS)[number], LucideIcon> = {
  overview: Layers,
  sources: Database,
  memory: Brain,
  indexation: Package,
  quality: Sparkles,
  access: Users,
  retention: Clock,
  lineage: GitBranch,
  history: History,
};
const TABLE_VIEWS = new Set(["overview", "sources", "memory"]);
const MAX_PAGE_BUTTONS = 5;
const ROWS_PER_PAGE_OPTS = [10, 25, 50];

type T = ReturnType<typeof useTranslations<"sources">>;
type Data = SourcesData;
type Row = Data["sources"][number];
type View = (typeof VIEWS)[number];
type SortKey = "name" | "type" | "volume" | "citation";

function SourcesSkeleton() {
  return (
    <div className="flex min-w-0 animate-pulse flex-col gap-2.5" aria-hidden="true">
      <div className="h-[54px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]" />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: static placeholder list
            key={i}
            className="h-[88px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
          />
        ))}
      </div>
      <div className="h-9 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]" />
      <div className="h-[420px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]" />
    </div>
  );
}

export function SourcesOverview() {
  const t = useTranslations("sources");
  const locale = useLocale();
  const { data } = useQuery({
    queryKey: ["sources-overview", locale],
    queryFn: ({ signal }) => fetchSourcesOverview(locale, signal),
    staleTime: 60_000,
  });

  const [view, setView] = useState<View>("overview");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("overview");

  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const types = useMemo(() => (data ? [...new Set(data.sources.map((s) => s.type))] : []), [data]);

  const rows = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    let out = data.sources.filter((s) => {
      if (typeFilter !== "all" && s.type !== typeFilter) return false;
      if (scope !== "all" && !s.infra && !s.consumer_ids.includes(scope)) return false;
      if (!q) return true;
      return s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
    });
    if (sortKey) {
      const dir = sortDir === "asc" ? 1 : -1;
      out = [...out].sort((a, b) => {
        if (sortKey === "volume") return (a.volume_num - b.volume_num) * dir;
        if (sortKey === "citation") return (citeNum(a) - citeNum(b)) * dir;
        return a[sortKey].localeCompare(b[sortKey], "fr") * dir;
      });
    }
    return out;
  }, [data, search, typeFilter, scope, sortKey, sortDir]);

  // Per-tab lens over the (filtered/sorted) rows.
  const viewRows = useMemo(() => {
    if (view === "sources") return rows.filter((r) => !r.infra);
    if (view === "memory") return rows.filter((r) => r.infra);
    return rows;
  }, [rows, view]);

  if (!data) {
    return <SourcesSkeleton />;
  }

  // Detail opens as a right-entering drawer on click (no row selected by default).
  const selected: Row | null =
    selectedId && selectedId !== "__none__"
      ? (data.sources.find((s) => s.id === selectedId) ?? null)
      : null;

  const onSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  };
  const onSelect = (id: string) => {
    setSelectedId(id);
    setTab("overview");
  };
  const onExport = () => {
    const blob = new Blob([JSON.stringify(data.sources, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tessera-sources.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const isTable = TABLE_VIEWS.has(view);

  return (
    <div className="flex min-w-0 flex-col gap-2.5 text-[var(--tessera-text)]">
      <CommandBar t={t} note={data.readonly_note} onExport={onExport} />
      <TabStrip
        accent="blue"
        active={view}
        onChange={setView}
        data-testid="sources-tabs"
        items={VIEWS.map((v) => ({
          key: v,
          label: t(`tabs.${v}`),
          icon: VIEW_ICONS[v],
        }))}
      />

      {view === "overview" ? (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
          {data.kpis.map((kpi) => (
            <CompactKpi key={kpi.key} kpi={kpi} />
          ))}
        </div>
      ) : null}

      {isTable || view === "quality" ? (
        <FilterStrip
          t={t}
          search={search}
          onSearch={setSearch}
          typeFilter={typeFilter}
          onType={setTypeFilter}
          types={types}
          count={view === "quality" ? rows.length : viewRows.length}
          total={data.sources.length}
        />
      ) : null}

      {view === "quality" ? (
        <div className="flex min-w-0 flex-col gap-3">
          <Note text={t("quality.subtitle")} icon={<Sparkles className="h-3.5 w-3.5" />} />
          <QualitySignals t={t} rows={rows} />
          <QualityTable t={t} rows={rows} selectedId={selectedId} onSelect={onSelect} />
        </div>
      ) : isTable ? (
        <div className="flex min-w-0 flex-col gap-3">
          {view === "memory" ? (
            <Note text={t("view.memoryNote")} icon={<Database className="h-3.5 w-3.5" />} />
          ) : null}
          <SourceTable
            t={t}
            rows={viewRows}
            selectedId={selectedId}
            onSelect={onSelect}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={onSort}
          />
          {view === "overview" ? (
            <div className="grid items-start gap-3 xl:grid-cols-[minmax(0,1fr)_260px]">
              <div className="flex min-w-0 flex-col gap-3">
                <ActivityArea t={t} data={data} />
                <div className="grid gap-3 sm:grid-cols-2">
                  <ByType t={t} data={data} />
                  <ByVolume data={data} />
                  <ByCitation t={t} data={data} />
                  <ByLanguage data={data} />
                </div>
              </div>
              <RecentActivity t={t} data={data} />
            </div>
          ) : null}
        </div>
      ) : (
        <LensView t={t} view={view} data={data} onSelect={onSelect} />
      )}

      <Footer t={t} data={data} />

      {selected ? (
        <SourcesDrawer ariaLabel={selected.name} onClose={() => setSelectedId(null)}>
          <DetailPanel
            t={t}
            row={selected}
            tab={tab}
            onTab={setTab}
            onClose={() => setSelectedId(null)}
          />
        </SourcesDrawer>
      ) : null}
    </div>
  );
}

function citeNum(r: Row): number {
  const n = Number.parseFloat(r.citation);
  return Number.isNaN(n) ? -1 : n;
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({ t, note, onExport }: { t: T; note: string; onExport: () => void }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <ShieldCheck className="h-3.5 w-3.5" /> {note}
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          href={ASOF_HREF}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] hover:border-[#2e72d2]"
        >
          <CalendarClock className="h-4 w-4" /> {t("actions.asof")}
        </Link>
        <Button
          size="sm"
          variant="outline"
          onClick={onExport}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <Download className="h-4 w-4" /> {t("actions.export")}
        </Button>
      </div>
    </section>
  );
}

/** ⓘ for a sources metric/section — renders only when sources.explain.<k> exists. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("sources.explain");
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

function CompactKpi({ kpi }: { kpi: Data["kpis"][number] }) {
  return (
    <div className="flex h-[88px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <p className="flex items-center gap-1 text-[0.62rem] font-medium text-[var(--tessera-text-muted)]">
        <Truncate full={kpi.label} className="min-w-0">
          {kpi.label}
        </Truncate>
        <ExplainInfo k={kpi.key} title={kpi.label} />
      </p>
      <p className="mt-0.5 text-[1.25rem] font-semibold leading-none text-white">{kpi.value}</p>
      <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
    </div>
  );
}

function FilterStrip({
  t,
  search,
  onSearch,
  typeFilter,
  onType,
  types,
  count,
  total,
}: {
  t: T;
  search: string;
  onSearch: (v: string) => void;
  typeFilter: string;
  onType: (v: string) => void;
  types: string[];
  count: number;
  total: number;
}) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="relative min-w-[200px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          aria-label={t("filters.search")}
          placeholder={t("filters.search")}
          className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[#2e72d2]"
        />
      </div>
      <label className="relative shrink-0">
        <span className="sr-only">{t("filters.type")}</span>
        <select
          value={typeFilter}
          onChange={(e) => onType(e.target.value)}
          className="h-9 cursor-pointer appearance-none rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-3 pr-8 text-xs text-[var(--tessera-text)] outline-none hover:border-[#2e72d2] focus:border-[#2e72d2]"
        >
          <option value="all">
            {t("filters.type")}: {t("filters.all")}
          </option>
          {types.map((ty) => (
            <option key={ty} value={ty}>
              {t(`type.${ty}`)}
            </option>
          ))}
        </select>
        <ChevronsUpDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#87bfff]" />
      </label>
      <AgentScopeFilter />
      <span className="shrink-0 text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
        {count}/{total}
      </span>
    </section>
  );
}

// ── pagination + drawer (shared style: agents/connaissances) ─────────────────

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(MAX_PAGE_BUTTONS, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, totalPages - span + 1);
  return Array.from({ length: span }, (_, i) => first + i);
}

function PageArrow({
  t,
  dir,
  disabled,
  onClick,
}: {
  t: T;
  dir: "prev" | "next";
  disabled: boolean;
  onClick: () => void;
}) {
  const Icon = dir === "prev" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={dir === "prev" ? t("page.prev") : t("page.next")}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
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
        <PageArrow
          t={t}
          dir="prev"
          disabled={page <= 1}
          onClick={() => onPage(Math.max(1, page - 1))}
        />
        {pageWindow(page, totalPages).map((n) => (
          <button
            key={n}
            type="button"
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
            className={cn(
              "flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-[0.72rem] tabular-nums",
              n === page
                ? "border-[#5b8def]/60 bg-[#5b8def]/15 font-medium text-white"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {n}
          </button>
        ))}
        <PageArrow
          t={t}
          dir="next"
          disabled={page >= totalPages}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
        />
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

/** Right-entering overlay drawer anchored to the main content area. */
function SourcesDrawer({
  ariaLabel,
  onClose,
  children,
}: {
  ariaLabel: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  const [shown, setShown] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const FOCUSABLE = 'button, a[href], select, input, [tabindex]:not([tabindex="-1"])';
  // Focus into the drawer on open and return focus to the opener (the row) on close.
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    return () => opener?.focus?.();
  }, []);
  // Trap Tab inside the drawer (a non-modal <dialog open> isn't modal natively).
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
      // Vertical extent = the visible scroll viewport (main); horizontal extent =
      // the centred content column, so the panel sits over the table, not at the
      // far screen edge on wide viewports.
      const c = document.querySelector("[data-shell-content]") ?? m;
      const cr = c.getBoundingClientRect();
      // Span the content column so the panel's right edge lines up with the main
      // table's right border (not the screen edge); no right padding keeps it flush.
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
        aria-label={ariaLabel}
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
        {children}
      </dialog>
    </div>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

const COLS: { key: string; sort?: SortKey }[] = [
  { key: "name", sort: "name" },
  { key: "type", sort: "type" },
  { key: "classification" },
  { key: "volume", sort: "volume" },
  { key: "units" },
  { key: "languages" },
  { key: "freshness" },
  { key: "citation", sort: "citation" },
  { key: "usedBy" },
];
// Balanced fixed widths (table-fixed): wide enough for readable source names,
// narrow for the numeric columns. Percentages are scaled by the browser to fill.
const COL_W: Record<string, string> = {
  name: "w-[22%]",
  type: "w-[10%]",
  classification: "w-[10%]",
  volume: "w-[7%]",
  units: "w-[7%]",
  languages: "w-[9%]",
  freshness: "w-[10%]",
  citation: "w-[13%]",
  usedBy: "w-[12%]",
};

function SourceTable({
  t,
  rows,
  selectedId,
  onSelect,
  sortKey,
  sortDir,
  onSort,
}: {
  t: T;
  rows: Row[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sortKey: SortKey | null;
  sortDir: "asc" | "desc";
  onSort: (key: SortKey) => void;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 when the filtered set or page size changes.
  useEffect(() => setPage(1), [rows.length, perPage]);
  const total = rows.length;
  const pages = Math.max(1, Math.ceil(total / perPage));
  const safePage = Math.min(page, pages);
  const start = (safePage - 1) * perPage;
  const paged = rows.slice(start, start + perPage);
  return (
    <div
      data-testid="sources-table"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
    >
      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "truncate py-1.5 text-left font-medium",
                    COL_W[c.key],
                    c.key === "name" ? "pl-5 pr-2" : "px-2",
                  )}
                >
                  {c.sort ? (
                    <button
                      type="button"
                      onClick={() => onSort(c.sort as SortKey)}
                      aria-sort={
                        sortKey === c.sort
                          ? sortDir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-[var(--tessera-text)]"
                    >
                      {t(`col.${c.key}`)}
                      {sortKey === c.sort ? (
                        sortDir === "asc" ? (
                          <SortAsc className="h-3 w-3 text-[#87bfff]" />
                        ) : (
                          <SortDesc className="h-3 w-3 text-[#87bfff]" />
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
            {paged.map((s) => {
              const active = s.id === selectedId;
              const Icon = TYPE_ICON[s.type] ?? Database;
              return (
                <tr
                  key={s.id}
                  onClick={() => onSelect(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(s.id);
                    }
                  }}
                  tabIndex={0}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                  role="button"
                  aria-label={s.name}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="py-1.5 pl-5 pr-2">
                    <span className="flex items-center gap-1.5 text-[var(--tessera-text)]">
                      <Icon
                        className={cn(
                          "h-3 w-3 shrink-0",
                          TYPE_ICON_TONE[s.type] ?? "text-[#87bfff]",
                        )}
                      />
                      <Truncate full={s.name}>{s.name}</Truncate>
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {t(`type.${s.type}`)}
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={CLASS_BADGE[s.classification]}>
                      {t(`classification.${s.classification}`)}
                    </Badge>
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text)]">
                    {s.volume}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {s.units}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{s.languages}</td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{s.freshness}</td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {s.citation}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <span className="flex items-center gap-1.5">
                      <Users className="h-3 w-3 shrink-0 text-[#87bfff]" />
                      <Truncate full={s.used_by}>{s.used_by}</Truncate>
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="flex items-center justify-end gap-1 whitespace-nowrap">
                      <span className="text-[0.66rem] text-[#87bfff] opacity-0 transition-opacity group-hover:opacity-100">
                        {t("detail.open")}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#87bfff]" />
                    </span>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length + 1}
                  className="px-2 py-6 text-center text-[0.7rem] text-[var(--tessera-text-muted)]"
                >
                  {t("empty.rows")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pagination
        t={t}
        page={safePage}
        totalPages={pages}
        start={total === 0 ? 0 : start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
      />
    </div>
  );
}

// ── non-table lens views ─────────────────────────────────────────────────────

function LensView({
  t,
  view,
  data,
  onSelect,
}: {
  t: T;
  view: View;
  data: Data;
  onSelect: (id: string) => void;
}) {
  if (view === "indexation") return <IndexationView t={t} data={data} />;
  if (view === "access") return <AccessView t={t} data={data} onSelect={onSelect} />;
  if (view === "retention") return <RetentionView t={t} data={data} onSelect={onSelect} />;
  if (view === "lineage") return <LineageView t={t} data={data} />;
  return <HistoryView t={t} data={data} />;
}

// Shared row interactivity for the lens lists/tables (click -> open the drawer).
const ROW_INTERACT =
  "group cursor-pointer outline-none transition-colors hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]";
function rowKeyActivate(e: ReactKeyboardEvent<HTMLElement>, fn: () => void) {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fn();
  }
}

function IndexationView({ t, data }: { t: T; data: Data }) {
  const e = data.embedding;
  const facts: [string, string][] = [
    [t("view.model"), e.model],
    [t("view.dim"), e.dim],
    [t("view.distance"), e.distance],
    [t("view.topk"), e.topk],
    [t("view.chunks"), e.chunks],
    [t("view.documents"), e.documents],
    [t("view.languages"), e.languages],
  ];
  const corpus = data.sources.filter((s) => !s.infra);
  const max = Math.max(...corpus.map((s) => s.volume_num), 1);
  return (
    <div className="grid gap-3 xl:grid-cols-[320px_minmax(0,1fr)]">
      <Panel
        title={t("view.embeddings")}
        info={<ExplainInfo k="embeddings" title={t("view.embeddings")} />}
      >
        <dl className="flex flex-col gap-1.5 text-[0.7rem]">
          {facts.map(([k, v]) => (
            <KV key={k} label={k} value={v} />
          ))}
        </dl>
      </Panel>
      <Panel title={t("view.chunksBySource")}>
        <ul className="flex flex-col gap-1.5">
          {corpus.map((s) => (
            <li key={s.id} className="flex items-center gap-2 text-[0.66rem]">
              <Truncate full={s.name} className="w-44 shrink-0 text-[var(--tessera-text)]">
                {s.name}
              </Truncate>
              <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
                <div
                  className="h-full rounded-full bg-[#2e72d2]"
                  style={{ width: `${(s.volume_num / max) * 100}%` }}
                />
              </div>
              <span className="w-12 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
                {s.volume}
              </span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function AccessView({
  t,
  data,
  onSelect,
}: {
  t: T;
  data: Data;
  onSelect: (id: string) => void;
}) {
  return (
    <Panel title={t("view.access")} info={<ExplainInfo k="access" title={t("view.access")} />}>
      <p className="mb-2 text-[0.64rem] text-[var(--tessera-text-muted)]">{t("view.accessNote")}</p>
      <ul className="flex flex-col divide-y divide-[var(--tessera-border)]/60">
        {data.sources.map((s) => {
          const Icon = TYPE_ICON[s.type] ?? Database;
          return (
            <li
              key={s.id}
              onClick={() => onSelect(s.id)}
              onKeyDown={(e) => rowKeyActivate(e, () => onSelect(s.id))}
              tabIndex={0}
              // biome-ignore lint/a11y/useSemanticElements: a list row opens the detail drawer; keyboard + role provided.
              // biome-ignore lint/a11y/noNoninteractiveElementToInteractiveRole: same — the row is an interactive drawer trigger with keyboard support.
              role="button"
              aria-label={s.name}
              className={cn(
                "-mx-2 flex items-center justify-between gap-3 rounded-md px-2 py-1.5 text-[0.7rem]",
                ROW_INTERACT,
              )}
            >
              <span className="inline-flex min-w-0 items-center gap-1.5">
                <Icon
                  className={cn("h-3 w-3 shrink-0", TYPE_ICON_TONE[s.type] ?? "text-[#87bfff]")}
                />
                <Truncate full={s.name} className="text-[var(--tessera-text)]">
                  {s.name}
                </Truncate>
              </span>
              <span className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
                {s.detail.consumers?.items.map((c) => (
                  <span
                    key={c.agent_id}
                    title={c.label}
                    className="inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.6rem]"
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        VERDICT_DOT[c.tone] ?? VERDICT_DOT.muted,
                      )}
                    />
                    {c.name}
                  </span>
                ))}
                <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#87bfff]" />
              </span>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}

function RetentionView({
  t,
  data,
  onSelect,
}: {
  t: T;
  data: Data;
  onSelect: (id: string) => void;
}) {
  return (
    <Panel
      title={t("view.retention")}
      info={<ExplainInfo k="retention" title={t("view.retention")} />}
    >
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-2 py-1.5 font-medium">{t("col.name")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.type")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.retention")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.classification")}</th>
            <th className="w-6 px-2 py-1.5" aria-hidden="true" />
          </tr>
        </thead>
        <tbody>
          {data.sources.map((s) => (
            <tr
              key={s.id}
              onClick={() => onSelect(s.id)}
              onKeyDown={(e) => rowKeyActivate(e, () => onSelect(s.id))}
              tabIndex={0}
              // biome-ignore lint/a11y/useSemanticElements: a table row opens the detail drawer; keyboard + role provided.
              role="button"
              aria-label={s.name}
              className={cn("border-b border-[var(--tessera-border)]/60", ROW_INTERACT)}
            >
              <td className="px-2 py-1.5 text-[var(--tessera-text)]">{s.name}</td>
              <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                {t(`type.${s.type}`)}
              </td>
              <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                <span className="inline-flex items-center gap-1.5">
                  <Clock className="h-3 w-3 text-[#87bfff]" /> {s.retention}
                </span>
              </td>
              <td className="px-2 py-1.5">
                <Badge className={CLASS_BADGE[s.classification]}>
                  {t(`classification.${s.classification}`)}
                </Badge>
              </td>
              <td className="px-2 py-1.5 text-right">
                <ChevronRight className="ml-auto h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#87bfff]" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function LineageView({ t, data }: { t: T; data: Data }) {
  // Group sources by the products that consume them (real consumer_ids).
  const products = new Map<string, { name: string; sources: string[] }>();
  for (const s of data.sources) {
    for (const c of s.detail.consumers?.items ?? []) {
      const entry = products.get(c.agent_id) ?? { name: c.name, sources: [] };
      entry.sources.push(s.name);
      products.set(c.agent_id, entry);
    }
  }
  return (
    <Panel title={t("view.lineage")} info={<ExplainInfo k="lineage" title={t("view.lineage")} />}>
      <p className="mb-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {t("view.lineageNote")}
      </p>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {[...products.values()].map((p) => (
          <div
            key={p.name}
            className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <span className="inline-flex items-center gap-1.5 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              <GitBranch className="h-3.5 w-3.5 text-[#87bfff]" /> {p.name}
            </span>
            <ul className="flex flex-col gap-0.5 text-[0.64rem] text-[var(--tessera-text-muted)]">
              {p.sources.map((name) => (
                <li key={name} className="truncate">
                  {name}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function HistoryView({ t, data }: { t: T; data: Data }) {
  const withGrowth = data.sources.filter((s) => s.growth.length > 0);
  const corpus = data.sources.filter((s) => s.growth.length === 0);
  return (
    <div className="flex flex-col gap-3">
      <Panel
        title={t("view.memoryGrowth")}
        info={<ExplainInfo k="memoryGrowth" title={t("view.memoryGrowth")} />}
      >
        <p className="mb-2 inline-flex items-center gap-1.5 text-[0.64rem] text-amber-300/90">
          <AlertTriangle className="h-3.5 w-3.5" /> {t("view.historyNote")}
        </p>
        <div className="grid gap-3 md:grid-cols-2">
          {withGrowth.map((s) => (
            <GrowthCard key={s.id} t={t} source={s} />
          ))}
        </div>
      </Panel>
      <Panel title={t("view.corpusHeading")}>
        <ul className="flex flex-col divide-y divide-[var(--tessera-border)]/60">
          {corpus.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-1.5 text-[0.7rem]">
              <Truncate full={s.name} className="text-[var(--tessera-text)]">
                {s.name}
              </Truncate>
              <span className="inline-flex shrink-0 items-center gap-1.5 text-[var(--tessera-text-muted)]">
                <Clock className="h-3 w-3" /> {t("view.lastIndexed")}: {s.freshness}
              </span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function GrowthCard({ t, source }: { t: T; source: Row }) {
  const total = source.growth.reduce((sum, d) => sum + d.count, 0);
  const first = source.growth.at(0)?.day ?? "";
  const last = source.growth.at(-1)?.day ?? "";
  return (
    <div className="flex flex-col gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="inline-flex min-w-0 items-center gap-1.5 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
          <Database className="h-3.5 w-3.5 shrink-0 text-[#87bfff]" />
          <Truncate full={source.name}>{source.name}</Truncate>
        </span>
        <span className="shrink-0 text-[0.62rem] text-[var(--tessera-text-muted)]">
          {t("view.total")}:{" "}
          <span className="tabular-nums text-white">{total.toLocaleString("fr-FR")}</span>
        </span>
      </div>
      <MetricSparkline
        className="h-10 w-full"
        values={source.growth.map((d) => d.count)}
        tone="success"
      />
      <div className="flex items-center justify-between text-[0.56rem] tabular-nums text-[var(--tessera-text-muted)]">
        <span>{first}</span>
        <span>{last}</span>
      </div>
    </div>
  );
}

// ── bottom charts ────────────────────────────────────────────────────────────

// Real memory activity: merge the two memory stores' daily growth into one
// wide area curve (the normative's prominent time-series). No fabricated axis -
// the corpus has none, but the memory tables span weeks of real created_at.
function ActivityArea({ t, data }: { t: T; data: Data }) {
  const byDay = new Map<string, number>();
  for (const s of data.sources) {
    for (const d of s.growth) byDay.set(d.day, (byDay.get(d.day) ?? 0) + d.count);
  }
  const days = [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b));
  if (days.length < 2) return null;
  const W = 600;
  const H = 80;
  const max = Math.max(...days.map(([, n]) => n), 1);
  const step = W / (days.length - 1);
  const pts = days.map(([, n], i) => [i * step, H - (n / max) * (H - 8)] as const);
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `M0,${H} L${line.replaceAll(" ", " L")} L${W},${H} Z`;
  const fmtMax = max.toLocaleString("fr-FR");
  return (
    <Panel title={t("view.activity")}>
      <div className="flex gap-2">
        {/* y reference: peak at top, zero at bottom */}
        <div className="flex shrink-0 flex-col justify-between py-0.5 text-right text-[0.5rem] tabular-nums leading-none text-[var(--tessera-text-muted)]">
          <span>{fmtMax}</span>
          <span>0</span>
        </div>
        <div className="min-w-0 flex-1">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-16 w-full"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <title>{t("view.activity")}</title>
            <defs>
              <linearGradient id="sm-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#34d399" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* peak + baseline reference lines */}
            <line
              x1="0"
              y1="8"
              x2={W}
              y2="8"
              stroke="var(--tessera-border)"
              strokeDasharray="3 4"
            />
            <line x1="0" y1={H} x2={W} y2={H} stroke="var(--tessera-border)" />
            <path d={area} fill="url(#sm-area)" />
            <polyline points={line} fill="none" stroke="#34d399" strokeWidth="1.5" />
          </svg>
          <div className="mt-1 flex items-center justify-between text-[0.56rem] tabular-nums text-[var(--tessera-text-muted)]">
            <span>{days.at(0)?.[0]}</span>
            <span>{days.at(-1)?.[0]}</span>
          </div>
        </div>
      </div>
    </Panel>
  );
}

// Tone -> dot colour for the activity feed.
const SUG_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  good: "bg-emerald-400",
  muted: "bg-[var(--tessera-text-muted)]",
};

// Real sources & memory lifecycle events (corpus indexing, memory writes,
// transcript growth) - NOT the agent's reasoning turns.
function RecentActivity({ t, data }: { t: T; data: Data }) {
  const { activity } = data;
  return (
    <Panel title={activity.title}>
      {activity.items.length === 0 ? (
        <p className="py-1 text-[0.72rem] text-[var(--tessera-text-muted)]">{activity.empty}</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {activity.items.map((e, i) => (
            <li key={`${e.time}-${e.text}-${i}`} className="relative flex gap-2.5 text-[0.72rem]">
              {/* connecting thread, centered on the dot column (w-4 -> 8px) */}
              {i < activity.items.length - 1 ? (
                <span
                  aria-hidden
                  className="-translate-x-1/2 absolute top-[7px] left-2 h-[calc(100%+0.625rem)] w-px bg-[var(--tessera-border)]"
                />
              ) : null}
              <span className="flex w-4 shrink-0 justify-center">
                <span
                  className={cn(
                    "z-10 mt-1 h-1.5 w-1.5 rounded-full ring-2 ring-[var(--tessera-surface)]",
                    SUG_DOT[e.tone] ?? "bg-slate-400",
                  )}
                />
              </span>
              <span className="min-w-0">
                <span className="block tabular-nums text-[var(--tessera-text-muted)]">
                  {e.time}
                </span>
                <span className="text-[var(--tessera-text)]">{e.text}</span>
                {e.actor ? (
                  <span className="block text-[0.66rem] text-[var(--tessera-text-muted)]">
                    {t("activitySubject")}{" "}
                    <span className="font-mono text-[var(--tessera-text)]">{e.actor}</span>
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ByType({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={data.zones.by_type}>
      <Donut slices={data.by_type} total={data.by_type_total} labelOf={(k) => t(`type.${k}`)} />
    </Panel>
  );
}

function ByVolume({ data }: { data: Data }) {
  return (
    <Panel title={data.zones.by_env}>
      <ul className="flex flex-col gap-2">
        {data.by_env.map((e) => (
          <li key={e.key} className="flex flex-col gap-0.5 text-[0.66rem]">
            <div className="flex items-center justify-between gap-1.5">
              <Truncate full={e.label} className="text-[var(--tessera-text)]">
                {e.label}
              </Truncate>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">
                {e.value} / {e.pct}%
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${e.pct}%`, background: e.color }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// Real per-source citation rate (from the cached retrieval probe).
function ByCitation({ t, data }: { t: T; data: Data }) {
  const rows = data.sources
    .map((s) => ({ name: s.name, pct: Number.parseFloat(s.citation) }))
    .filter((r) => !Number.isNaN(r.pct))
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 6);
  return (
    <Panel
      title={t("view.citationBySource")}
      info={<ExplainInfo k="citationBySource" title={t("view.citationBySource")} />}
    >
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.name} className="flex flex-col gap-1 text-[0.66rem]">
            <div className="flex items-center justify-between gap-2">
              <Truncate full={r.name} className="min-w-0 text-[var(--tessera-text)]">
                {r.name}
              </Truncate>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {Math.round(r.pct)}%
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full bg-[#34d399]"
                style={{ width: `${Math.min(100, r.pct)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function ByLanguage({ data }: { data: Data }) {
  const max = Math.max(...data.cost_by_source.map((c) => c.value), 1);
  return (
    <Panel title={data.zones.cost}>
      <ul className="flex flex-col gap-2">
        {data.cost_by_source.map((c) => (
          <li key={c.name} className="flex items-center gap-2 text-[0.66rem]">
            <Truncate
              full={c.name}
              className="w-10 shrink-0 font-medium text-[var(--tessera-text)]"
            >
              {c.name}
            </Truncate>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(c.value / max) * 100}%`, background: c.color ?? "#2e72d2" }}
              />
            </div>
            <span className="w-20 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {c.label}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

// ── quality & freshness lens ───────────────────────────────────────────────

function median(nums: number[]): number | null {
  if (nums.length === 0) return null;
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  const hi = s[mid] ?? 0;
  if (s.length % 2) return hi;
  const lo = s[mid - 1] ?? hi;
  return (lo + hi) / 2;
}

function QualitySignals({ t, rows }: { t: T; rows: Row[] }) {
  const corpus = rows.filter((r) => r.citation_pct !== null);
  const freshDays = rows.map((r) => r.freshness_days).filter((d): d is number => d !== null);
  const medFresh = median(freshDays);
  const medCite = median(corpus.map((r) => r.citation_pct as number));
  const watch = rows.filter((r) => r.quality_tone === "warn").length;
  const cards: { key: string; label: string; value: string; tone?: string }[] = [
    { key: "evaluated", label: t("quality.signalEvaluated"), value: String(corpus.length) },
    {
      key: "freshness",
      label: t("quality.signalFreshness"),
      value: medFresh === null ? "—" : `${medFresh} ${t("quality.daysUnit")}`,
    },
    {
      key: "citation",
      label: t("quality.signalCitation"),
      value: medCite === null ? "—" : `${Math.round(medCite)} %`,
    },
    {
      key: "watch",
      label: t("quality.signalWatch"),
      value: String(watch),
      tone: watch > 0 ? "warn" : "good",
    },
  ];
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      {cards.map((c) => (
        <div
          key={c.key}
          className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5"
        >
          <p className="text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {c.label}
          </p>
          <p
            className={cn(
              "mt-1 font-mono text-[0.95rem] font-semibold",
              c.tone === "warn" ? "text-amber-300" : "text-white",
            )}
          >
            {c.value}
          </p>
        </div>
      ))}
    </div>
  );
}

type QSort = "freshness" | "citation";

function QualityTable({
  t,
  rows,
  selectedId,
  onSelect,
}: {
  t: T;
  rows: Row[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [sortKey, setSortKey] = useState<QSort | null>(null);
  const [dir, setDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const onSort = (k: QSort) => {
    if (sortKey === k) setDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setDir("desc");
    }
  };
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 when the set/sort/size changes.
  useEffect(() => setPage(1), [rows.length, perPage, sortKey, dir]);
  const sorted = useMemo(() => {
    const arr = [...rows];
    if (!sortKey) {
      // Default lens: rows to watch first, then most stale (oldest) first.
      return arr.sort((a, b) => {
        const aw = a.quality_tone === "warn" ? 0 : 1;
        const bw = b.quality_tone === "warn" ? 0 : 1;
        if (aw !== bw) return aw - bw;
        return (b.freshness_days ?? -1) - (a.freshness_days ?? -1);
      });
    }
    const m = dir === "asc" ? 1 : -1;
    return arr.sort((a, b) => {
      if (sortKey === "freshness") return ((a.freshness_days ?? -1) - (b.freshness_days ?? -1)) * m;
      return ((a.citation_pct ?? -1) - (b.citation_pct ?? -1)) * m;
    });
  }, [rows, sortKey, dir]);

  const total = sorted.length;
  const pages = Math.max(1, Math.ceil(total / perPage));
  const safePage = Math.min(page, pages);
  const start = (safePage - 1) * perPage;
  const paged = sorted.slice(start, start + perPage);

  if (total === 0) {
    return (
      <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-[0.72rem] text-[var(--tessera-text-muted)]">
        {t("quality.empty")}
      </p>
    );
  }

  const sortHead = (key: QSort, label: string, width: string) => (
    <th className={cn("truncate px-2 py-1.5 font-medium", width)}>
      <button
        type="button"
        onClick={() => onSort(key)}
        className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-[var(--tessera-text)]"
      >
        {label}
        {sortKey === key ? (
          dir === "asc" ? (
            <SortAsc className="h-3 w-3 text-[#87bfff]" />
          ) : (
            <SortDesc className="h-3 w-3 text-[#87bfff]" />
          )
        ) : (
          <ChevronsUpDown className="h-3 w-3 opacity-40" />
        )}
      </button>
    </th>
  );

  return (
    <div
      data-testid="quality-table"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
    >
      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="w-[26%] truncate py-1.5 pl-5 pr-2 font-medium">
                {t("quality.colSource")}
              </th>
              <th className="w-[12%] truncate px-2 py-1.5 font-medium">{t("quality.colType")}</th>
              {sortHead("freshness", t("quality.colFreshness"), "w-[12%]")}
              {sortHead("citation", t("quality.colCitation"), "w-[15%]")}
              <th className="w-[8%] truncate px-2 py-1.5 font-medium">{t("quality.colHits")}</th>
              <th className="w-[14%] truncate px-2 py-1.5 font-medium">
                {t("quality.colVersion")}
              </th>
              <th className="w-[13%] truncate px-2 py-1.5 font-medium">{t("quality.colState")}</th>
              <th className="w-28 px-2 py-1.5" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {paged.map((s) => {
              const active = s.id === selectedId;
              const warn = s.quality_tone === "warn";
              const Icon = TYPE_ICON[s.type] ?? Database;
              return (
                <tr
                  key={s.id}
                  onClick={() => onSelect(s.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(s.id);
                    }
                  }}
                  tabIndex={0}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                  role="button"
                  aria-label={s.name}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="py-1.5 pl-5 pr-2">
                    <span className="flex items-center gap-1.5 text-[var(--tessera-text)]">
                      <Icon
                        className={cn(
                          "h-3 w-3 shrink-0",
                          TYPE_ICON_TONE[s.type] ?? "text-[#87bfff]",
                        )}
                      />
                      <Truncate full={s.name}>{s.name}</Truncate>
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {t(`type.${s.type}`)}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{s.freshness}</td>
                  <td className="px-2 py-1.5">
                    {s.citation_pct === null ? (
                      <span className="text-[var(--tessera-text-muted)]">{t("quality.na")}</span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-[4px] w-14 overflow-hidden rounded-full bg-[var(--tessera-border)]">
                          <span
                            className="block h-full rounded-full bg-[#5b8def]"
                            style={{ width: `${Math.min(100, s.citation_pct)}%` }}
                          />
                        </span>
                        <span className="tabular-nums text-[var(--tessera-text)]">
                          {s.citation}
                        </span>
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {s.hits}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <span className="inline-flex items-center gap-1.5">
                      <Tag className="h-3 w-3 shrink-0 text-[#87bfff]" />
                      <Truncate full={s.version}>{s.version}</Truncate>
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[0.6rem]",
                        warn
                          ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                          : "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
                      )}
                    >
                      {warn ? (
                        <AlertTriangle className="h-3 w-3" />
                      ) : (
                        <CheckCircle2 className="h-3 w-3" />
                      )}
                      {s.quality_label}
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="flex items-center justify-end gap-1 whitespace-nowrap">
                      <span className="text-[0.66rem] text-[#87bfff] opacity-0 transition-opacity group-hover:opacity-100">
                        {t("detail.open")}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#87bfff]" />
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Pagination
        t={t}
        page={safePage}
        totalPages={pages}
        start={start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
      />
    </div>
  );
}

function DetailPanel({
  t,
  row,
  tab,
  onTab,
  onClose,
}: {
  t: T;
  row: Row | null;
  tab: string;
  onTab: (tab: string) => void;
  onClose: () => void;
}) {
  if (!row) {
    return (
      <aside
        data-testid="source-detail"
        className="flex min-w-0 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6 text-center xl:sticky xl:top-0 xl:h-fit xl:min-h-[200px]"
      >
        <Database className="h-5 w-5 text-[var(--tessera-text-muted)]" />
        <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{t("detail.selectHint")}</p>
      </aside>
    );
  }
  const detail = row.detail;
  const section = detail.sections.find((s) => s.key === tab) ?? detail.sections[0];
  if (!section) return null;
  const tags = [
    ...(row.languages !== "-" ? row.languages.split("/") : []),
    t(`type.${row.type}`),
    t(`classification.${row.classification}`),
  ];
  return (
    <aside
      data-testid="source-detail"
      className="flex h-full w-full min-w-0 flex-col gap-3 overflow-y-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Truncate as="p" full={detail.name} className="text-sm font-semibold text-white">
            {detail.name}
          </Truncate>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge className={CLASS_BADGE[detail.classification]}>
              {t(`classification.${detail.classification}`)}
            </Badge>
            <span
              className={cn(
                "inline-flex items-center gap-1 text-[0.62rem]",
                STATUS[detail.status].text,
              )}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[detail.status].dot)} />{" "}
              {t(`status.${detail.status}`)}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {row.infra ? null : (
            <Link
              href={{ pathname: "/prouver/etat-a-date", query: { sources: row.id } }}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.64rem] text-[var(--tessera-text-muted)] hover:border-[#2e72d2] hover:text-[var(--tessera-text)]"
            >
              <CalendarClock className="h-3.5 w-3.5" /> {t("detail.asof")}
            </Link>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label={t("detail.close")}
            className="text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Ring kept tight on the left; the divider sits midway between the ring and
          the chunks column because divider/cols/edge share space evenly. */}
      <div className="flex items-stretch rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] py-3.5 pl-5">
        <div className="relative left-2 flex flex-col items-center justify-center gap-1.5">
          <ScoreRing value={row.citation} />
          <span className="text-[0.58rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {t("detail.score")}
          </span>
        </div>
        <div className="flex flex-1 items-stretch justify-evenly">
          <div className="w-px self-stretch bg-[var(--tessera-border)]" />
          <dl className="flex flex-col justify-center gap-3.5">
            <Fact
              icon={<Layers className="h-3.5 w-3.5" />}
              label={t("detail.tChunks")}
              value={row.volume}
            />
            <Fact
              icon={<Database className="h-3.5 w-3.5" />}
              label={t("col.languages")}
              value={row.languages}
            />
          </dl>
          <dl className="flex flex-col justify-center gap-3.5">
            <Fact
              icon={<Boxes className="h-3.5 w-3.5" />}
              label={t("detail.tDocuments")}
              value={row.units}
            />
            <Fact
              icon={<ShieldCheck className="h-3.5 w-3.5" />}
              label={t("detail.tHits")}
              value={String(row.hits)}
            />
          </dl>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[var(--tessera-border)] pb-2">
        {detail.sections.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => onTab(s.key)}
            className={cn(
              "rounded px-2 py-1 text-[0.62rem] font-medium",
              s.key === section.key
                ? "bg-[#0d3561] text-[#d8eaff]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
            )}
          >
            {s.title}
          </button>
        ))}
      </div>

      {tab === "overview" || section.key === "overview" ? (
        <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text)]">
          {detail.description}
        </p>
      ) : null}

      <dl className="flex flex-col gap-1 text-[0.66rem]">
        {section.rows.map((r) => (
          <KV key={r.label} label={r.label} value={r.value} />
        ))}
      </dl>

      <div className="flex flex-wrap gap-1">
        {tags.map((tag) => (
          <span
            key={tag}
            className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.64rem] text-[var(--tessera-text-muted)]"
          >
            {tag}
          </span>
        ))}
      </div>

      {section.key === "content" && detail.versions ? (
        <VersionsBlock t={t} versions={detail.versions} />
      ) : null}

      {section.key === "governance" && detail.consumers ? (
        <UsedByBlock consumers={detail.consumers} />
      ) : null}
    </aside>
  );
}

function VersionsBlock({
  t,
  versions,
}: {
  t: T;
  versions: NonNullable<Row["detail"]["versions"]>;
}) {
  return (
    <div className="border-t border-[var(--tessera-border)] pt-2" data-testid="source-versions">
      <div className="mb-1.5 inline-flex items-center gap-1.5 text-[0.66rem] font-semibold text-[var(--tessera-text)]">
        <History className="h-3.5 w-3.5 text-[#87bfff]" /> {versions.title}
      </div>
      {versions.drift?.changed ? (
        <p className="mb-1.5 inline-flex items-center gap-1 rounded-md border border-amber-400/40 bg-amber-400/10 px-2 py-1 text-[0.64rem] text-amber-300">
          <AlertTriangle className="h-3 w-3" /> {versions.drift.label}
        </p>
      ) : null}
      <p className="mb-1 text-[0.64rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {versions.current_title}
      </p>
      <dl className="mb-2 flex flex-col gap-1 text-[0.62rem]">
        {versions.current.map((r) => (
          <KV key={r.label} label={r.label} value={r.value} />
        ))}
      </dl>
      <p className="mb-1 text-[0.64rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {versions.runs_title}
      </p>
      {versions.runs.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {versions.runs.map((run) => (
            <li
              key={run.run_id}
              className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-[0.62rem]"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 font-medium text-[var(--tessera-text)]">
                  <GitBranch className="h-3 w-3 text-[#87bfff]" /> {run.run_id}
                  {run.language !== "-" ? (
                    <span className="rounded border border-[var(--tessera-border)] px-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
                      {run.language}
                    </span>
                  ) : null}
                </span>
                <span className="tabular-nums text-[var(--tessera-text-muted)]">{run.when}</span>
              </div>
              <p className="mt-0.5 text-[var(--tessera-text-muted)]">
                {run.model} · {run.chunks} {t("version.chunksUnit")} · {run.chunking} ·{" "}
                {run.trigger}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="rounded-md border border-dashed border-[var(--tessera-border)] px-2 py-1.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {versions.empty}
        </p>
      )}
      <p className="mt-1.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {versions.note}
      </p>
    </div>
  );
}

function UsedByBlock({ consumers }: { consumers: NonNullable<Row["detail"]["consumers"]> }) {
  return (
    <div className="border-t border-[var(--tessera-border)] pt-2">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 text-[0.66rem] font-semibold text-[var(--tessera-text)]">
          <Users className="h-3.5 w-3.5 text-[#87bfff]" /> {consumers.title}
        </span>
        {consumers.regate_count > 0 ? (
          <span className="inline-flex items-center gap-1 text-[0.64rem] text-amber-300">
            <AlertTriangle className="h-3 w-3" /> {consumers.regate_label}
          </span>
        ) : null}
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {consumers.items.map((c) => (
          <li
            key={c.agent_id}
            title={c.label}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.62rem]"
          >
            <span
              className={cn("h-1.5 w-1.5 rounded-full", VERDICT_DOT[c.tone] ?? VERDICT_DOT.muted)}
            />
            {c.name}
          </li>
        ))}
      </ul>
      <p className="mt-1.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {consumers.note}
      </p>
      {consumers.count > 0 ? (
        <Link
          href={REVALIDATE_HREF}
          className={cn(
            "mt-1.5 inline-flex items-center gap-1 text-[0.64rem] font-medium hover:underline",
            consumers.model_changed ? "text-amber-300" : "text-[#87bfff]",
          )}
        >
          <GitBranch className="h-3 w-3" /> {consumers.revalidate_label}
        </Link>
      ) : null}
    </div>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Note({ text, icon }: { text: string; icon: ReactNode }) {
  return (
    <p className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
      <span className="text-[#87bfff]">{icon}</span> {text}
    </p>
  );
}

function Fact({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="flex items-center gap-1.5 text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        <span className="shrink-0 text-[#87bfff]">{icon}</span>
        <span className="truncate">{label}</span>
      </dt>
      <dd className="mt-1 truncate text-[0.82rem] font-semibold leading-none tabular-nums text-white">
        {value}
      </dd>
    </div>
  );
}

// A single-arc score ring (the real citation rate); "-" renders an empty ring.
function ScoreRing({ value }: { value: string }) {
  const pct = Number.parseFloat(value);
  const has = !Number.isNaN(pct);
  const R = 27;
  const C = 2 * Math.PI * R;
  const filled = has ? Math.min(100, Math.max(0, pct)) : 0;
  return (
    <div className="relative h-[68px] w-[68px] shrink-0">
      <svg viewBox="0 0 68 68" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="34" cy="34" r={R} fill="none" stroke="var(--tessera-border)" strokeWidth="6" />
        {has ? (
          <circle
            cx="34"
            cy="34"
            r={R}
            fill="none"
            stroke="#34d399"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${(filled / 100) * C} ${C}`}
          />
        ) : null}
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[1.05rem] font-semibold tabular-nums text-white">
          {has ? `${Math.round(pct)}%` : "-"}
        </span>
      </div>
    </div>
  );
}

function Panel({
  title,
  info,
  children,
}: { title: string; info?: ReactNode; children: ReactNode }) {
  return (
    <div
      data-slot="card"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3"
    >
      <h3 className="mb-2 flex items-center gap-1 text-[0.72rem] font-semibold uppercase leading-tight tracking-wide text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{title}</span>
        {info}
      </h3>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function Donut({
  slices,
  total,
  labelOf,
}: {
  slices: Data["by_type"];
  total: number;
  labelOf: (key: string) => string;
}) {
  const sum = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[84px] w-[84px] shrink-0">
        <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="36"
            cy="36"
            r={R}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="9"
          />
          {slices.map((s) => {
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
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-base font-semibold tabular-nums text-white">{total}</span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.62rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <Truncate full={labelOf(s.key)} className="min-w-0 flex-1 text-[var(--tessera-text)]">
              {labelOf(s.key)}
            </Truncate>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {s.count} / {s.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.64rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0 truncate text-right text-[var(--tessera-text)]">{value}</dd>
    </div>
  );
}

function Footer({ t, data }: { t: T; data: Data }) {
  // Provenance only — the "this is live, not a fixture" proof. The redundant
  // total and the divider rule were dropped; the table + KPIs already carry the
  // count. The raw table names are the honesty signal on an operator cockpit.
  return (
    <footer className="mt-1 shrink-0 pb-4 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span>{t("footer.source", { src: data.footer.source.replaceAll(" + ", " · ") })}</span>
    </footer>
  );
}

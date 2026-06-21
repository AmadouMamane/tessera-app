"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Boxes,
  CalendarClock,
  ChevronsUpDown,
  Clock,
  Database,
  Download,
  GitBranch,
  Layers,
  Search,
  ShieldCheck,
  SortAsc,
  SortDesc,
  Users,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
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
const KNOWLEDGE_HREF = "/agent/connaissances";
const ASOF_HREF = "/prouver/etat-a-date";
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
const TABLE_VIEWS = new Set(["overview", "sources", "memory", "quality"]);

type T = ReturnType<typeof useTranslations<"sources">>;
type Data = SourcesData;
type Row = Data["sources"][number];
type View = (typeof VIEWS)[number];
type SortKey = "name" | "type" | "volume" | "citation";

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
    if (view === "quality" && !sortKey) return [...rows].sort((a, b) => citeNum(b) - citeNum(a));
    return rows;
  }, [rows, view, sortKey]);

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  // Persistent detail like the normative: default to the first source; an
  // explicit close ("__none__") falls back to the empty hint.
  const selected: Row | null =
    selectedId === "__none__"
      ? null
      : selectedId
        ? (data.sources.find((s) => s.id === selectedId) ?? null)
        : (data.sources[0] ?? null);

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
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} note={data.readonly_note} onExport={onExport} />
      <TabStrip t={t} view={view} onView={setView} />

      {view === "overview" ? (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
          {data.kpis.map((kpi) => (
            <CompactKpi key={kpi.key} kpi={kpi} />
          ))}
        </div>
      ) : null}

      {isTable ? (
        <FilterStrip
          t={t}
          search={search}
          onSearch={setSearch}
          typeFilter={typeFilter}
          onType={setTypeFilter}
          types={types}
          count={viewRows.length}
          total={data.sources.length}
        />
      ) : null}

      {isTable ? (
        <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">
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
              <>
                <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
                  <ActivityArea t={t} data={data} />
                  <Suggestions data={data} />
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <ByType t={t} data={data} />
                  <ByVolume data={data} />
                  <ByCitation t={t} data={data} />
                  <ByLanguage data={data} />
                </div>
              </>
            ) : null}
          </div>
          <DetailPanel
            t={t}
            row={selected}
            tab={tab}
            onTab={setTab}
            onClose={() => setSelectedId("__none__")}
          />
        </div>
      ) : (
        <LensView t={t} view={view} data={data} />
      )}

      {view === "overview" ? <LineageFooter data={data} /> : null}
      <Footer t={t} data={data} />
    </div>
  );
}

function citeNum(r: Row): number {
  const n = Number.parseFloat(r.citation);
  return Number.isNaN(n) ? -1 : n;
}

// ── chrome ───────────────────────────────────────────────────────────────────

function TabStrip({ t, view, onView }: { t: T; view: View; onView: (v: View) => void }) {
  return (
    <nav
      data-testid="sources-tabs"
      className="flex shrink-0 flex-wrap items-center gap-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 py-1.5"
    >
      {VIEWS.map((v) => (
        <button
          key={v}
          type="button"
          aria-current={v === view ? "page" : undefined}
          onClick={() => onView(v)}
          className={cn(
            "rounded-md px-2.5 py-1.5 text-[0.7rem] font-medium transition-colors",
            v === view
              ? "bg-[#0d3561] text-[#d8eaff]"
              : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
          )}
        >
          {t(`tabs.${v}`)}
        </button>
      ))}
    </nav>
  );
}

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
        <Link
          href={KNOWLEDGE_HREF}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
        >
          <Database className="h-4 w-4" /> {t("actions.manage")}
        </Link>
      </div>
    </section>
  );
}

function CompactKpi({ kpi }: { kpi: Data["kpis"][number] }) {
  return (
    <div className="flex h-[88px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <p className="truncate text-[0.62rem] font-medium text-[var(--tessera-text-muted)]">
        {kpi.label}
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
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c) => (
                <th key={c.key} className="whitespace-nowrap px-2 py-1.5 font-medium">
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
                      className="inline-flex items-center gap-1 hover:text-[var(--tessera-text)]"
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
            </tr>
          </thead>
          <tbody>
            {paged.map((s) => {
              const active = s.id === selectedId;
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
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="px-2 py-1.5">
                    <span className="inline-flex items-center gap-1.5 text-[var(--tessera-text)]">
                      <Database className="h-3 w-3 text-[#87bfff]" /> {s.name}
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
                    <span className={cn("inline-flex items-center gap-1.5", s.infra && "italic")}>
                      <Users className="h-3 w-3 shrink-0 text-[#87bfff]" />
                      <span className="truncate">{s.used_by}</span>
                    </span>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length}
                  className="px-2 py-6 text-center text-[0.7rem] text-[var(--tessera-text-muted)]"
                >
                  {t("empty.rows")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span className="tabular-nums">
          {total === 0 ? 0 : start + 1}-{Math.min(start + perPage, total)} {t("page.of")} {total}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={safePage <= 1}
            aria-label={t("page.prev")}
            className="rounded border border-[var(--tessera-border)] px-1.5 py-0.5 disabled:opacity-40 hover:enabled:border-[#2e72d2]"
          >
            ‹
          </button>
          <span className="tabular-nums">
            {safePage}/{pages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={safePage >= pages}
            aria-label={t("page.next")}
            className="rounded border border-[var(--tessera-border)] px-1.5 py-0.5 disabled:opacity-40 hover:enabled:border-[#2e72d2]"
          >
            ›
          </button>
          <label className="ml-1 inline-flex items-center gap-1">
            <span className="sr-only">{t("page.perPage")}</span>
            <select
              value={perPage}
              onChange={(e) => setPerPage(Number(e.target.value))}
              className="cursor-pointer appearance-none rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[var(--tessera-text)] hover:border-[#2e72d2]"
            >
              {[10, 25, 50].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
    </div>
  );
}

// ── non-table lens views ─────────────────────────────────────────────────────

function LensView({ t, view, data }: { t: T; view: View; data: Data }) {
  if (view === "indexation") return <IndexationView t={t} data={data} />;
  if (view === "access") return <AccessView t={t} data={data} />;
  if (view === "retention") return <RetentionView t={t} data={data} />;
  if (view === "lineage") return <LineageView t={t} data={data} />;
  return <HistoryView t={t} data={data} />;
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
      <Panel title={t("view.embeddings")}>
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
              <span className="w-44 shrink-0 truncate text-[var(--tessera-text)]">{s.name}</span>
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

function AccessView({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("view.access")}>
      <p className="mb-2 text-[0.64rem] text-[var(--tessera-text-muted)]">{t("view.accessNote")}</p>
      <ul className="flex flex-col divide-y divide-[var(--tessera-border)]/60">
        {data.sources.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-3 py-1.5 text-[0.7rem]">
            <span className="inline-flex min-w-0 items-center gap-1.5">
              <Database className="h-3 w-3 shrink-0 text-[#87bfff]" />
              <span className="truncate text-[var(--tessera-text)]">{s.name}</span>
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
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function RetentionView({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("view.retention")}>
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-2 py-1.5 font-medium">{t("col.name")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.type")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.retention")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.classification")}</th>
          </tr>
        </thead>
        <tbody>
          {data.sources.map((s) => (
            <tr key={s.id} className="border-b border-[var(--tessera-border)]/60">
              <td className="px-2 py-1.5 text-[var(--tessera-text)]">{s.name}</td>
              <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                {t(`type.${s.type}`)}
              </td>
              <td className="px-2 py-1.5 inline-flex items-center gap-1.5 text-[var(--tessera-text-muted)]">
                <Clock className="h-3 w-3 text-[#87bfff]" /> {s.retention}
              </td>
              <td className="px-2 py-1.5">
                <Badge className={CLASS_BADGE[s.classification]}>
                  {t(`classification.${s.classification}`)}
                </Badge>
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
    <Panel title={t("view.lineage")}>
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
      <Panel title={t("view.memoryGrowth")}>
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
              <span className="truncate text-[var(--tessera-text)]">{s.name}</span>
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
          <span className="truncate">{source.name}</span>
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
  return (
    <Panel title={t("view.activity")}>
      <div className="flex items-end justify-between gap-2 text-[0.56rem] tabular-nums text-[var(--tessera-text-muted)]">
        <span>{days.at(0)?.[0]}</span>
        <span>{days.at(-1)?.[0]}</span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="mt-1 h-20 w-full"
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
        <path d={area} fill="url(#sm-area)" />
        <polyline points={line} fill="none" stroke="#34d399" strokeWidth="1.5" />
      </svg>
    </Panel>
  );
}

// Real derived recommendations (low-citation sources, re-validation blast radius,
// memory growth, the honest negligible indexing cost). Each may deep-link.
const SUG_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  good: "bg-emerald-400",
  muted: "bg-[var(--tessera-text-muted)]",
};

function Suggestions({ data }: { data: Data }) {
  return (
    <Panel title={data.suggestions.title}>
      <ul className="flex flex-col gap-2">
        {data.suggestions.items.map((s) => {
          const body = (
            <span className="inline-flex items-start gap-2">
              <span className={cn("mt-1 h-1.5 w-1.5 shrink-0 rounded-full", SUG_DOT[s.tone])} />
              <span className="text-[var(--tessera-text)]">{s.text}</span>
            </span>
          );
          return (
            <li key={s.text} className="text-[0.66rem] leading-relaxed">
              {s.href ? (
                <Link
                  href={s.href as never}
                  className="block rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 hover:border-[#2e72d2]"
                >
                  {body}
                </Link>
              ) : (
                <span className="block rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5">
                  {body}
                </span>
              )}
            </li>
          );
        })}
      </ul>
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
              <span className="truncate text-[var(--tessera-text)]">{e.label}</span>
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
    <Panel title={t("view.citationBySource")}>
      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.name} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-28 shrink-0 truncate text-[var(--tessera-text)]">{r.name}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full bg-[#34d399]"
                style={{ width: `${Math.min(100, r.pct)}%` }}
              />
            </div>
            <span className="w-9 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {Math.round(r.pct)}%
            </span>
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
            <span className="w-10 shrink-0 truncate font-medium text-[var(--tessera-text)]">
              {c.name}
            </span>
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
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:sticky xl:top-0 xl:h-fit"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{detail.name}</p>
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
        <button
          type="button"
          onClick={onClose}
          aria-label={t("detail.close")}
          className="text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex items-center gap-3 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
        <ScoreRing value={row.citation} caption={t("detail.score")} />
        <dl className="grid min-w-0 flex-1 grid-cols-2 gap-x-3 gap-y-1 text-[0.62rem]">
          <Fact
            icon={<Layers className="h-3 w-3" />}
            label={t("detail.tChunks")}
            value={row.volume}
          />
          <Fact
            icon={<Boxes className="h-3 w-3" />}
            label={t("detail.tDocuments")}
            value={row.units}
          />
          <Fact
            icon={<Database className="h-3 w-3" />}
            label={t("col.languages")}
            value={row.languages}
          />
          <Fact
            icon={<ShieldCheck className="h-3 w-3" />}
            label={t("detail.tHits")}
            value={String(row.hits)}
          />
        </dl>
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
            className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.56rem] text-[var(--tessera-text-muted)]"
          >
            {tag}
          </span>
        ))}
      </div>

      {detail.consumers ? <UsedByBlock consumers={detail.consumers} /> : null}
    </aside>
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
          <span className="inline-flex items-center gap-1 text-[0.6rem] text-amber-300">
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
      <p className="mt-1.5 text-[0.56rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {consumers.note}
      </p>
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
      <dt className="inline-flex items-center gap-1 truncate text-[0.54rem] text-[var(--tessera-text-muted)]">
        <span className="text-[#87bfff]">{icon}</span> {label}
      </dt>
      <dd className="truncate text-[0.78rem] font-semibold tabular-nums text-white">{value}</dd>
    </div>
  );
}

// A single-arc score ring (the real citation rate); "-" renders an empty ring.
function ScoreRing({ value, caption }: { value: string; caption: string }) {
  const pct = Number.parseFloat(value);
  const has = !Number.isNaN(pct);
  const R = 24;
  const C = 2 * Math.PI * R;
  const filled = has ? Math.min(100, Math.max(0, pct)) : 0;
  return (
    <div className="relative h-[64px] w-[64px] shrink-0">
      <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="32" cy="32" r={R} fill="none" stroke="var(--tessera-border)" strokeWidth="6" />
        {has ? (
          <circle
            cx="32"
            cy="32"
            r={R}
            fill="none"
            stroke="#34d399"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={`${(filled / 100) * C} ${C}`}
          />
        ) : null}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-[0.82rem] font-semibold tabular-nums text-white">
          {has ? `${Math.round(pct)}%` : "-"}
        </span>
        <span className="px-1 text-[0.4rem] uppercase leading-tight text-[var(--tessera-text-muted)]">
          {caption}
        </span>
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="mb-2 truncate text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {title}
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
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
              {labelOf(s.key)}
            </span>
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
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.56rem] font-medium",
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

// The normative footer: the real source-to-answer lineage + audit-chain integrity.
function LineageFooter({ data }: { data: Data }) {
  const { lineage, audit } = data;
  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
          {lineage.title}
        </h3>
        <span className="inline-flex items-center gap-2 text-[0.62rem] text-[var(--tessera-text-muted)]">
          <span className="inline-flex items-center gap-1.5">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                audit.tone === "good" ? "bg-emerald-400" : "bg-red-400",
              )}
            />
            <span className={audit.tone === "good" ? "text-emerald-300" : "text-red-300"}>
              {audit.label}
            </span>
          </span>
          <span className="hidden sm:inline">
            {audit.checked_label} : {audit.checked}
          </span>
        </span>
      </div>
      <div className="flex flex-wrap items-stretch gap-1.5">
        {lineage.steps.map((s, i) => {
          const inner = (
            <div className="flex h-full min-w-[120px] flex-col rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5">
              <span className="text-[0.52rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {s.label}
              </span>
              <span className="truncate text-[0.68rem] font-medium text-[var(--tessera-text)]">
                {s.value}
              </span>
            </div>
          );
          return (
            <div key={s.key} className="flex items-center gap-1.5">
              {s.href ? (
                <Link href={s.href as never} className="hover:opacity-80">
                  {inner}
                </Link>
              ) : (
                inner
              )}
              {i < lineage.steps.length - 1 ? (
                <span className="text-[var(--tessera-text-muted)]">→</span>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
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

"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronsUpDown,
  Database,
  Download,
  Search,
  ShieldCheck,
  SortAsc,
  SortDesc,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useMemo, useState } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
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

type T = ReturnType<typeof useTranslations<"sources">>;
type Data = SourcesData;
type Row = Data["sources"][number];
type Detail = Row["detail"];
type SortKey = "name" | "type" | "volume" | "citation";

export function SourcesOverview() {
  const t = useTranslations("sources");
  const locale = useLocale();
  const { data } = useQuery({
    queryKey: ["sources-overview", locale],
    queryFn: ({ signal }) => fetchSourcesOverview(locale, signal),
    staleTime: 60_000,
  });

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("overview");

  const types = useMemo(() => (data ? [...new Set(data.sources.map((s) => s.type))] : []), [data]);

  const rows = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    let out = data.sources.filter((s) => {
      if (typeFilter !== "all" && s.type !== typeFilter) return false;
      if (!q) return true;
      return s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
    });
    if (sortKey) {
      const dir = sortDir === "asc" ? 1 : -1;
      out = [...out].sort((a, b) => {
        if (sortKey === "volume") return (a.volume_num - b.volume_num) * dir;
        if (sortKey === "citation") {
          const na = Number.parseFloat(a.citation) || -1;
          const nb = Number.parseFloat(b.citation) || -1;
          return (na - nb) * dir;
        }
        return a[sortKey].localeCompare(b[sortKey], "fr") * dir;
      });
    }
    return out;
  }, [data, search, typeFilter, sortKey, sortDir]);

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  const selected: Detail | null =
    (selectedId && data.sources.find((s) => s.id === selectedId)?.detail) || null;

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

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} note={data.readonly_note} onExport={onExport} />

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} />
        ))}
      </div>

      <FilterStrip
        t={t}
        search={search}
        onSearch={setSearch}
        typeFilter={typeFilter}
        onType={setTypeFilter}
        types={types}
        count={rows.length}
        total={data.sources.length}
      />

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-3">
          <SourceTable
            t={t}
            rows={rows}
            selectedId={selectedId}
            onSelect={onSelect}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={onSort}
          />
          <div className="grid gap-3 xl:grid-cols-3">
            <ByType t={t} data={data} />
            <ByVolume data={data} />
            <ByLanguage data={data} />
          </div>
        </div>
        <DetailPanel
          t={t}
          detail={selected}
          tab={tab}
          onTab={setTab}
          onClose={() => setSelectedId(null)}
        />
      </div>

      <Footer t={t} data={data} />
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({ t, note, onExport }: { t: T; note: string; onExport: () => void }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <ShieldCheck className="h-3.5 w-3.5" /> {note}
      </span>
      <div className="flex flex-wrap items-center gap-2">
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
            {rows.map((s) => {
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
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>{t("footer.total", { n: rows.length })}</span>
      </div>
    </div>
  );
}

// ── bottom charts ────────────────────────────────────────────────────────────

function ByType({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={data.zones.by_type}>
      <Donut slices={data.by_type} total={data.by_type_total} labelOf={(k) => t(`type.${k}`)} />
    </Panel>
  );
}

function ByVolume({ data }: { data: Data }) {
  const max = Math.max(...data.by_env.map((e) => Number(e.value.replace(/\s/g, "")) || 0), 1);
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
                style={{
                  width: `${((Number(e.value.replace(/\s/g, "")) || 0) / max) * 100}%`,
                  background: e.color,
                }}
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
  detail,
  tab,
  onTab,
  onClose,
}: {
  t: T;
  detail: Detail | null;
  tab: string;
  onTab: (tab: string) => void;
  onClose: () => void;
}) {
  if (!detail) {
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
  const section = detail.sections.find((s) => s.key === tab) ?? detail.sections[0];
  if (!section) return null;
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
    </aside>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

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

function Footer({ t, data }: { t: T; data: Data }) {
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span>{t("footer.total", { n: data.footer.total })}</span>
      <span>{t("footer.source", { src: data.footer.source })}</span>
    </footer>
  );
}

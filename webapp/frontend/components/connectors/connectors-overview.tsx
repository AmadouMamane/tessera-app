"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDown, Plug, Search, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useMemo, useState } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { fetchConnectors } from "@/lib/api/client";
import type { ConnectorsOverview as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"connectors">>;
type Cx = NonNullable<Data["connectors"]>[number];

const STATUS: Record<string, { dot: string; text: string }> = {
  active: { dot: "bg-emerald-400", text: "text-emerald-300" },
  standby: { dot: "bg-slate-400", text: "text-slate-300" },
  degraded: { dot: "bg-amber-400", text: "text-amber-300" },
  error: { dot: "bg-red-400", text: "text-red-300" },
};
const CAT_BADGE: Record<string, string> = {
  llm: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  retrieval: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  guard: "border-red-500/30 bg-red-500/15 text-red-300",
  secrets: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  observability: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  infra: "border-slate-500/30 bg-slate-500/15 text-slate-300",
};
type SortKey = "name" | "category" | "status" | "environment";

export function ConnectorsOverview() {
  const t = useTranslations("connectors");
  const { data } = useQuery({
    queryKey: ["connectors"],
    queryFn: ({ signal }) => fetchConnectors(signal),
    staleTime: 60_000,
  });

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "name", dir: 1 });
  const [open, setOpen] = useState<Cx | null>(null);

  const connectors = useMemo(() => data?.connectors ?? [], [data]);
  const categories = useMemo(
    () => Array.from(new Set(connectors.map((c) => c.category))),
    [connectors],
  );
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = connectors.filter((c) => {
      if (category !== "all" && c.category !== category) return false;
      if (status !== "all" && c.status !== status) return false;
      if (!q) return true;
      return `${c.name} ${c.description} ${c.role}`.toLowerCase().includes(q);
    });
    return [...filtered].sort((a, b) => a[sort.key].localeCompare(b[sort.key]) * sort.dir);
  }, [connectors, query, category, status, sort]);

  if (!data) return <Loading />;
  if (!data.available) return <Unavailable text={t("unavailable")} />;

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <p className="text-sm text-[var(--tessera-text-muted)]">{t("subtitle")}</p>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {(data.kpis ?? []).map((k) => (
          <div
            key={k.key}
            className="flex h-[92px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5"
          >
            <p className="truncate text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
              {t(`kpi.${k.key}`)}
            </p>
            <p className="mt-0.5 text-[1.3rem] font-semibold leading-none text-white">{k.value}</p>
            <p className="mt-0.5 truncate text-[0.56rem] text-[var(--tessera-text-muted)]">
              {k.sub}
            </p>
            <MetricSparkline className="mt-auto h-4 w-full" values={k.series} tone="success" />
          </div>
        ))}
      </div>

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-3">
          <FilterStrip
            t={t}
            query={query}
            onQuery={setQuery}
            category={category}
            onCategory={setCategory}
            status={status}
            onStatus={setStatus}
            categories={categories}
          />
          <Table t={t} rows={rows} sort={sort} onSort={toggleSort} onOpen={setOpen} />
        </div>
        <Distribution t={t} data={data} />
      </div>

      {data.footer ? (
        <footer className="mt-1 flex flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
          <span>{t("footer.total", { n: data.footer.total ?? rows.length })}</span>
          <span>{t("footer.source", { src: data.footer.source })}</span>
        </footer>
      ) : null}

      {open ? <CxDrawer t={t} cx={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

function FilterStrip({
  t,
  query,
  onQuery,
  category,
  onCategory,
  status,
  onStatus,
  categories,
}: {
  t: T;
  query: string;
  onQuery: (v: string) => void;
  category: string;
  onCategory: (v: string) => void;
  status: string;
  onStatus: (v: string) => void;
  categories: string[];
}) {
  return (
    <section className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <div className="relative min-w-[200px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          value={query}
          onChange={(e) => onQuery(e.target.value)}
          placeholder={t("search")}
          className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
        />
      </div>
      <select
        value={category}
        onChange={(e) => onCategory(e.target.value)}
        className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
      >
        <option value="all">{t("allCategories")}</option>
        {categories.map((c) => (
          <option key={c} value={c}>
            {t(`category.${c}`)}
          </option>
        ))}
      </select>
      <select
        value={status}
        onChange={(e) => onStatus(e.target.value)}
        className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
      >
        <option value="all">{t("allStatuses")}</option>
        {(["active", "standby", "degraded", "error"] as const).map((s) => (
          <option key={s} value={s}>
            {t(`status.${s}`)}
          </option>
        ))}
      </select>
    </section>
  );
}

function Table({
  t,
  rows,
  sort,
  onSort,
  onOpen,
}: {
  t: T;
  rows: Cx[];
  sort: { key: SortKey; dir: 1 | -1 };
  onSort: (k: SortKey) => void;
  onOpen: (c: Cx) => void;
}) {
  const cols: { key: SortKey; sortable: true }[] = [
    { key: "name", sortable: true },
    { key: "category", sortable: true },
    { key: "status", sortable: true },
    { key: "environment", sortable: true },
  ];
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.74rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c.key} className="px-3 py-2 font-medium">
                  <button
                    type="button"
                    onClick={() => onSort(c.key)}
                    aria-sort={
                      sort.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"
                    }
                    className="inline-flex items-center gap-1 hover:text-[var(--tessera-text)]"
                  >
                    {t(`col.${c.key}`)}
                    <ChevronsUpDown
                      className={cn(
                        "h-3 w-3",
                        sort.key === c.key ? "text-[var(--tessera-green)]" : "opacity-40",
                      )}
                    />
                  </button>
                </th>
              ))}
              <th className="px-3 py-2 font-medium">{t("col.latency")}</th>
              <th className="px-3 py-2 font-medium">{t("col.lastCheck")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.id}
                onClick={() => onOpen(c)}
                className="cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors hover:bg-[var(--tessera-muted)]"
              >
                <td className="px-3 py-2">
                  <span className="flex items-center gap-2">
                    <span className="grid h-6 w-6 shrink-0 place-items-center rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                      <Plug className="h-3 w-3" />
                    </span>
                    <span className="font-medium text-[var(--tessera-text)]">{c.name}</span>
                  </span>
                </td>
                <td className="px-3 py-2">
                  <Badge className={CAT_BADGE[c.category]}>{t(`category.${c.category}`)}</Badge>
                </td>
                <td className="px-3 py-2">
                  <span className={cn("inline-flex items-center gap-1.5", STATUS[c.status]?.text)}>
                    <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[c.status]?.dot)} />
                    {t(`status.${c.status}`)}
                  </span>
                </td>
                <td className="px-3 py-2 text-[var(--tessera-text-muted)]">{c.environment}</td>
                <td className="px-3 py-2 tabular-nums text-[var(--tessera-text-muted)]">
                  {c.latency}
                </td>
                <td className="px-3 py-2 text-[var(--tessera-text-muted)]">{c.last_check}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        {t("rowCount", { n: rows.length })}
      </div>
    </div>
  );
}

function Distribution({ t, data }: { t: T; data: Data }) {
  return (
    <aside className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:h-fit">
      <h3 className="text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {t("byCategory")}
      </h3>
      {(data.distribution ?? []).map((s) => (
        <div key={s.key} className="flex items-center gap-2 text-[0.7rem]">
          <span className="w-24 shrink-0 truncate">{t(`category.${s.key}`)}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
            <div
              className="h-full rounded-full"
              style={{ width: `${s.pct}%`, background: s.color }}
            />
          </div>
          <span className="w-12 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
            {s.count}
          </span>
        </div>
      ))}
    </aside>
  );
}

function CxDrawer({ t, cx, onClose }: { t: T; cx: Cx; onClose: () => void }) {
  const meta: [string, string][] = [
    [t("drawer.role"), cx.role],
    [t("drawer.endpoint"), cx.endpoint],
    [t("drawer.auth"), cx.auth],
    [t("drawer.version"), cx.version],
    [t("drawer.environment"), cx.environment],
    [t("drawer.latency"), cx.latency],
    [t("drawer.lastCheck"), cx.last_check],
  ];
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <dialog
        open
        aria-modal
        className="relative m-0 flex h-full w-full max-w-[460px] flex-col gap-4 overflow-y-auto border-l border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className={CAT_BADGE[cx.category]}>{t(`category.${cx.category}`)}</Badge>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 text-[0.66rem]",
                  STATUS[cx.status]?.text,
                )}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[cx.status]?.dot)} />
                {t(`status.${cx.status}`)}
              </span>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-white">{cx.name}</h2>
            <p className="mt-1 font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">{cx.id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("drawer.close")}
            className="shrink-0 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <p className="text-[0.8rem] leading-relaxed text-[var(--tessera-text)]">{cx.description}</p>
        <dl className="flex flex-col gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[0.72rem]">
          {meta.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-3">
              <dt className="shrink-0 text-[var(--tessera-text-muted)]">{k}</dt>
              <dd className="min-w-0 truncate text-right font-mono text-[0.68rem] text-[var(--tessera-text)]">
                {v}
              </dd>
            </div>
          ))}
        </dl>
      </dialog>
    </div>
  );
}

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

function Loading() {
  return (
    <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
      …
    </div>
  );
}

function Unavailable({ text }: { text: string }) {
  return (
    <div className="flex min-h-[200px] flex-1 items-center justify-center rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-8 text-center text-sm text-[var(--tessera-text-muted)]">
      {text}
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Download,
  Lock,
  Search,
  ShieldAlert,
  SortAsc,
  SortDesc,
  Users,
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
import { Link } from "@/i18n/navigation";
import { fetchAccessOverview } from "@/lib/api/client";
import type { AccessOverviewPayload as AccessData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const TYPE_BADGE: Record<string, string> = {
  systeme: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  metier: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const STATUS_TEXT: Record<string, string> = {
  active: "text-[var(--tessera-fg-success)]",
  deprecated: "text-[var(--tessera-fg-warning)]",
  disabled: "text-[var(--tessera-text-muted)]",
};
const DETAIL_TABS = ["overview", "permissions", "users", "groups", "history"] as const;
const USERS_HREF = "/admin/utilisateurs";

type DetailTab = (typeof DETAIL_TABS)[number];
type T = ReturnType<typeof useTranslations<"roles">>;
type Data = AccessData;
type Role = Data["roles"][number];
type SortKey = "name" | "type" | "users" | "permissions" | "modified";

/** ⓘ for a roles/access KPI or section, reading roles.explain.<k>.{what,how,source?}. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("roles.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

export function AccessOverview() {
  const t = useTranslations("roles");
  const tt = useTranslations("table");
  const locale = useLocale();
  const { data: response } = useQuery({
    queryKey: ["access-overview", locale],
    queryFn: ({ signal }) => fetchAccessOverview(locale, signal),
    staleTime: 60_000,
  });

  // Honest-empty, narrowed ONCE (audit P1.4). The backend answers `{available: false}` — and
  // nothing else — when the roles store is unreachable, so the page degrades instead of breaking.
  // Until now the schema REQUIRED the payload, so zod rejected that answer and `request()` threw:
  // the page broke on the exact response that exists to keep it standing, and it broke precisely
  // when the backend was already failing. Narrowing here means every reader below sees either the
  // whole payload or nothing — the union is handled, not ignored.
  const data: AccessData | undefined = response?.available ? response : undefined;
  // `=== false`, not `!response?.available`: while the query is still in flight `response` is
  // undefined, and treating that as "unavailable" would render the outage card over a page that
  // is merely loading. Degraded and loading are different states and must render differently.
  const unavailable = response?.available === false;

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "systeme" | "metier">("all");
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("overview");

  const rows = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    let out = data.roles.filter((r) => {
      if (typeFilter !== "all" && r.type !== typeFilter) return false;
      if (!q) return true;
      return (
        r.name.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.id.toLowerCase().includes(q)
      );
    });
    if (sortKey) {
      const dir = sortDir === "asc" ? 1 : -1;
      out = [...out].sort((a, b) => {
        if (sortKey === "users") return (a.users - b.users) * dir;
        if (sortKey === "permissions") return (a.permissions - b.permissions) * dir;
        return a[sortKey].localeCompare(b[sortKey], "fr") * dir;
      });
    }
    return out;
  }, [data, search, typeFilter, sortKey, sortDir]);

  // The degraded state is a RENDER, not a crash — and it is distinct from "still loading". An
  // empty spinner would claim the page is on its way; it is not, and saying so is the point.
  if (unavailable) {
    return (
      <div data-testid="access-unavailable" className="flex h-full items-center justify-center p-8">
        <div className="max-w-md text-center">
          <p className="text-sm font-medium text-[var(--tessera-text)]">{t("unavailableTitle")}</p>
          <p className="mt-2 text-sm text-[var(--tessera-text-muted)]">{t("unavailable")}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  const selected: Role | null = (selectedId && data.roles.find((r) => r.id === selectedId)) || null;

  const onSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const onSelect = (id: string) => {
    setSelectedId(id);
    setTab("overview");
  };

  const onExport = () => {
    const blob = new Blob([JSON.stringify(data.roles, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tessera-roles.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <CommandBar t={t} onExport={onExport} />

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((kpi) => (
          <CompactKpi
            key={kpi.key}
            kpi={kpi}
            label={t(`kpi.${kpi.key}`)}
            info={<ExplainInfo k={kpi.key} title={t(`kpi.${kpi.key}`)} />}
          />
        ))}
      </div>

      <FilterStrip
        t={t}
        search={search}
        onSearch={setSearch}
        typeFilter={typeFilter}
        onType={setTypeFilter}
        count={rows.length}
        total={data.roles.length}
      />

      <RoleTable
        t={t}
        tt={tt}
        rows={rows}
        selectedId={selectedId}
        onSelect={onSelect}
        sortKey={sortKey}
        sortDir={sortDir}
        onSort={onSort}
      />

      <div className="grid min-w-0 items-start gap-3 xl:grid-cols-3">
        <TopRoles t={t} data={data} />
        <ByResource t={t} data={data} />
        <Pending t={t} data={data} />
      </div>
      <div className="grid min-w-0 items-start gap-3 xl:grid-cols-2">
        <SodViolations t={t} data={data} />
        <Inactive t={t} data={data} />
      </div>

      <Footer t={t} data={data} />

      {selected ? (
        <RoleDrawer
          t={t}
          role={selected}
          tab={tab}
          onTab={setTab}
          onClose={() => setSelectedId(null)}
        />
      ) : null}
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({ t, onExport }: { t: T; onExport: () => void }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center justify-between gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <Lock className="h-3.5 w-3.5" /> {t("readonlyNote")}
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
          href={USERS_HREF}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
        >
          <Users className="h-4 w-4" /> {t("actions.viewUsers")}
        </Link>
      </div>
    </section>
  );
}

function CompactKpi({
  kpi,
  label,
  info,
}: { kpi: Data["kpis"][number]; label: string; info?: ReactNode }) {
  return (
    <div className="flex h-[92px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <p className="flex items-center gap-1 text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
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
  search,
  onSearch,
  typeFilter,
  onType,
  count,
  total,
}: {
  t: T;
  search: string;
  onSearch: (v: string) => void;
  typeFilter: "all" | "systeme" | "metier";
  onType: (v: "all" | "systeme" | "metier") => void;
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
          onChange={(e) => onType(e.target.value as "all" | "systeme" | "metier")}
          className="h-9 cursor-pointer appearance-none rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-3 pr-8 text-xs text-[var(--tessera-text)] outline-none hover:border-[#2e72d2] focus:border-[#2e72d2]"
        >
          <option value="all">
            {t("filters.type")}: {t("filters.all")}
          </option>
          <option value="systeme">{t("type.systeme")}</option>
          <option value="metier">{t("type.metier")}</option>
        </select>
        <ChevronsUpDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--tessera-fg-info)]" />
      </label>
      <span className="shrink-0 text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
        {count}/{total}
      </span>
    </section>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

const COLS: { key: string; sort?: SortKey; w: string }[] = [
  { key: "name", sort: "name", w: "16%" },
  { key: "type", sort: "type", w: "9%" },
  { key: "description", w: "19%" },
  { key: "users", sort: "users", w: "6%" },
  { key: "groups", w: "6%" },
  { key: "permissions", sort: "permissions", w: "8%" },
  { key: "scope", w: "10%" },
  { key: "environment", w: "10%" },
  { key: "modified", sort: "modified", w: "9%" },
  { key: "status", w: "7%" },
];
const ROWS_PER_PAGE_OPTS = [10, 25, 50];

function RoleTable({
  t,
  tt,
  rows,
  selectedId,
  onSelect,
  sortKey,
  sortDir,
  onSort,
}: {
  t: T;
  tt: ReturnType<typeof useTranslations<"table">>;
  rows: Role[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sortKey: SortKey | null;
  sortDir: "asc" | "desc";
  onSort: (key: SortKey) => void;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on filter/sort/size change
  useEffect(() => setPage(1), [total, perPage, sortKey, sortDir]);
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * perPage;
  const pageRows = rows.slice(start, start + perPage);
  return (
    <div
      data-testid="roles-table"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] table-fixed border-collapse text-left text-[0.72rem]">
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
            {pageRows.map((r) => {
              const active = r.id === selectedId;
              return (
                <tr
                  key={r.id}
                  onClick={() => onSelect(r.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(r.id);
                    }
                  }}
                  tabIndex={0}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                  role="button"
                  aria-label={r.name}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors last:border-0 hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="py-1.5 pl-5 pr-2 font-medium text-[var(--tessera-text)]">
                    <Truncate full={r.name}>{r.name}</Truncate>
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={TYPE_BADGE[r.type]}>{t(`type.${r.type}`)}</Badge>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={r.description}>{r.description}</Truncate>
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text)]">{r.users}</td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.groups}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.permissions}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={r.scope}>{r.scope}</Truncate>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={r.environment}>{r.environment}</Truncate>
                  </td>
                  <td className="px-2 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    <Truncate full={r.modified}>{r.modified}</Truncate>
                  </td>
                  <td className="px-2 py-1.5">
                    <span className={cn("inline-flex items-center gap-1", STATUS_TEXT[r.status])}>
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          r.status === "active" ? "bg-emerald-400" : "bg-amber-400",
                        )}
                      />{" "}
                      {t(`status.${r.status}`)}
                    </span>
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
                  {t("empty.roles")}
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
      />
    </div>
  );
}

// ── bottom panels ────────────────────────────────────────────────────────────

// Shared connaissances-style pagination footer.
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
}: {
  tt: ReturnType<typeof useTranslations<"table">>;
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

function TopRoles({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.top_roles.map((r) => r.value), 1);
  return (
    <Panel
      title={t("zone.topRoles")}
      info={<ExplainInfo k="topRoles" title={t("zone.topRoles")} />}
    >
      <ul className="flex flex-col gap-2">
        {data.top_roles.map((r) => (
          <li key={r.name} className="flex items-center gap-2 text-[0.66rem]">
            <Truncate full={r.name} className="w-24 shrink-0 text-[var(--tessera-text)]">
              {r.name}
            </Truncate>
            <div className="h-[4px] overflow-hidden flex-1 rounded-full bg-[var(--tessera-border)]">
              <div
                className="h-full rounded-full bg-[#2e72d2]"
                style={{ width: `${(r.value / max) * 100}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {r.label}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function ByResource({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.access_by_resource.map((r) => r.count), 1);
  return (
    <Panel
      title={t("zone.byResource")}
      info={<ExplainInfo k="byResource" title={t("zone.byResource")} />}
    >
      <ul className="flex flex-col gap-2">
        {data.access_by_resource.map((r) => (
          <li key={r.key} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-28 shrink-0 truncate text-[var(--tessera-text)]">
              {t(`resource.${r.key}`)}
            </span>
            <div className="h-[4px] overflow-hidden flex-1 rounded-full bg-[var(--tessera-border)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(r.count / max) * 100}%`, background: r.color }}
              />
            </div>
            <span className="w-14 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {r.count} / {r.pct}%
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function EmptyHint({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-md border border-dashed border-[var(--tessera-border)] px-2 py-3 text-center text-[0.62rem] text-[var(--tessera-text-muted)]">
      {children}
    </p>
  );
}

function Pending({ t, data }: { t: T; data: Data }) {
  return (
    <Panel
      title={t("zone.pending")}
      info={<ExplainInfo k="pending" title={t("zone.pending")} />}
      action={<AuditLink label={t("drill.audit")} />}
    >
      {data.pending_requests.length === 0 ? (
        <EmptyHint>{t("empty.pending")}</EmptyHint>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.pending_requests.map((p) => (
            <li key={p.user} className="flex items-center gap-2 text-[0.66rem]">
              <span className="font-medium text-[var(--tessera-text)]">{p.user}</span>
              <Truncate full={p.role} className="min-w-0 flex-1 text-[var(--tessera-text-muted)]">
                {p.role}
              </Truncate>
              <span className="shrink-0 text-[var(--tessera-text-muted)]">{p.since}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function SodViolations({ t, data }: { t: T; data: Data }) {
  return (
    <Panel
      title={t("zone.sod")}
      info={<ExplainInfo k="sod" title={t("zone.sod")} />}
      action={<AuditLink label={t("drill.audit")} />}
    >
      {data.sod_violations.length === 0 ? (
        <EmptyHint>{t("empty.sod")}</EmptyHint>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.sod_violations.map((v) => (
            <li key={v.user} className="flex items-center gap-2 text-[0.66rem]">
              <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-danger)]" />
              <span className="font-medium text-[var(--tessera-text)]">{v.user}</span>
              <Truncate
                full={v.conflict}
                className="min-w-0 flex-1 text-[var(--tessera-text-muted)]"
              >
                {v.conflict}
              </Truncate>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Inactive({ t, data }: { t: T; data: Data }) {
  return (
    <Panel
      title={t("zone.inactive")}
      info={<ExplainInfo k="inactive" title={t("zone.inactive")} />}
    >
      {data.inactive_accounts.length === 0 ? (
        <EmptyHint>{t("empty.inactive")}</EmptyHint>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.inactive_accounts.map((a) => (
            <li key={a.user} className="flex items-center gap-2 text-[0.66rem]">
              <span className="font-medium text-[var(--tessera-text)]">{a.user}</span>
              <Truncate full={a.role} className="min-w-0 flex-1 text-[var(--tessera-text-muted)]">
                {a.role}
              </Truncate>
              <span className="shrink-0 text-[var(--tessera-text-muted)]">{a.last_seen}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

function RoleDrawer({
  t,
  role,
  tab,
  onTab,
  onClose,
}: {
  t: T;
  role: Role;
  tab: DetailTab;
  onTab: (tab: DetailTab) => void;
  onClose: () => void;
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
  const meta: [string, string][] = [
    [t("detail.scope"), role.scope],
    [t("detail.owner"), role.owner],
    [t("detail.modified"), role.modified],
    [t("detail.environment"), role.environment],
  ];
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
        aria-label={role.name}
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
        <aside
          data-testid="role-detail"
          className="flex h-full w-full min-w-0 flex-col gap-3 overflow-y-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <Truncate
                as="p"
                full={role.name}
                className="text-sm font-semibold text-[var(--tessera-text-strong)]"
              >
                {role.name}
              </Truncate>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {role.id}
                </span>
                <Badge className={TYPE_BADGE[role.type]}>{t(`type.${role.type}`)}</Badge>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 text-[0.62rem]",
                    STATUS_TEXT[role.status],
                  )}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />{" "}
                  {t(`status.${role.status}`)}
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
            {DETAIL_TABS.map((dt) => (
              <button
                key={dt}
                type="button"
                onClick={() => onTab(dt)}
                className={cn(
                  "rounded px-2 py-1 text-[0.62rem] font-medium",
                  dt === tab
                    ? "bg-[#0d3561] text-[#d8eaff]"
                    : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
                )}
              >
                {t(`detailTabs.${dt}`)}
              </button>
            ))}
          </div>

          {tab === "overview" ? (
            <>
              <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text)]">
                {role.description}
              </p>
              <dl className="flex flex-col gap-1 text-[0.66rem]">
                {meta.map(([k, v]) => (
                  <KV key={k} label={k} value={v} />
                ))}
              </dl>
              <div className="grid grid-cols-2 gap-3 border-t border-[var(--tessera-border)] pt-2">
                <Distribution
                  title={t("detail.permDist")}
                  items={role.permission_dist}
                  labelOf={(k) => t(`perm.${k}`)}
                />
                <Distribution
                  title={t("detail.accessScope")}
                  items={role.access_scope}
                  labelOf={(k) => t(`resource.${k}`)}
                />
              </div>
            </>
          ) : null}

          {tab === "permissions" ? (
            <div>
              <p className="mb-1.5 text-[0.66rem] font-semibold text-[var(--tessera-text)]">
                {t("detail.capabilities")} ({role.caps.length})
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {role.caps.map((c) => (
                  <li
                    key={c}
                    className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.62rem] text-[var(--tessera-text)]"
                  >
                    {t(`cap.${c}`)}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {tab === "users" ? (
            <div>
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-[0.66rem] font-semibold text-[var(--tessera-text)]">
                  {t("detail.members")} ({role.members.length})
                </p>
                <Link
                  href={USERS_HREF}
                  className="text-[0.62rem] text-[var(--tessera-fg-info)] hover:text-[var(--tessera-text-strong)]"
                >
                  {t("detail.viewAll")} →
                </Link>
              </div>
              {role.members.length === 0 ? (
                <EmptyHint>{t("empty.members")}</EmptyHint>
              ) : (
                <ul className="flex flex-col gap-1">
                  {role.members.map((m) => (
                    <li key={m.name} className="flex items-center gap-2 text-[0.66rem]">
                      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-soft)] text-[0.56rem] font-semibold text-[var(--tessera-green)]">
                        {m.name.charAt(0).toUpperCase()}
                      </span>
                      <div className="min-w-0 flex-1">
                        <Truncate as="p" full={m.name} className="text-[var(--tessera-text)]">
                          {m.name}
                        </Truncate>
                        <Truncate
                          as="p"
                          full={m.team}
                          className="text-[0.56rem] text-[var(--tessera-text-muted)]"
                        >
                          {m.team}
                        </Truncate>
                      </div>
                      <span
                        className={cn(
                          "shrink-0",
                          m.status === "active"
                            ? "text-[var(--tessera-fg-success)]"
                            : "text-[var(--tessera-fg-warning)]",
                        )}
                      >
                        {t(`memberStatus.${m.status}`)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}

          {tab === "groups" ? <EmptyHint>{t("empty.groups")}</EmptyHint> : null}

          {tab === "history" ? (
            <dl className="flex flex-col gap-1 text-[0.66rem]">
              <KV label={t("detail.lastModified")} value={role.modified} />
              <KV label={t("detail.owner")} value={role.owner} />
              <KV label={t("detail.source")} value={t("readonlyNote")} />
            </dl>
          ) : null}
        </aside>
      </dialog>
    </div>
  );
}

function Distribution({
  title,
  items,
  labelOf,
}: {
  title: string;
  items: Role["permission_dist"];
  labelOf: (key: string) => string;
}) {
  return (
    <div>
      <p className="mb-1 text-[0.62rem] font-semibold text-[var(--tessera-text)]">{title}</p>
      <ul className="flex flex-col gap-1 text-[0.62rem]">
        {items.map((it) => (
          <li key={it.key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: it.color }} />
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
              {labelOf(it.key)}
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {it.count} ({it.pct}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Panel({
  title,
  info,
  action,
  children,
  className,
}: {
  title: string;
  info?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex min-w-0 items-center gap-1 text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
          <span className="min-w-0 truncate">{title}</span>
          {info}
        </h3>
        {action}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

/** Small "see → audit" drill used in a roles/access panel header. */
function AuditLink({ label }: { label: string }) {
  return (
    <Link
      href="/prouver/audit-logs"
      className="inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap text-[0.62rem] text-[var(--tessera-green)] hover:underline"
    >
      {label}
      <ChevronRight className="h-3 w-3" />
    </Link>
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
      <Truncate as="dd" full={value} className="min-w-0 text-right text-[var(--tessera-text)]">
        {value}
      </Truncate>
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

"use client";

import { useQuery } from "@tanstack/react-query";
import {
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
import { useTranslations } from "next-intl";
import { type ReactNode, useMemo, useState } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { fetchAccessOverview } from "@/lib/api/client";
import type { AccessOverview as AccessData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const TYPE_BADGE: Record<string, string> = {
  systeme: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  metier: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const STATUS_TEXT: Record<string, string> = {
  active: "text-emerald-300",
  deprecated: "text-amber-300",
  disabled: "text-[var(--tessera-text-muted)]",
};
const DETAIL_TABS = ["overview", "permissions", "users", "groups", "history"] as const;
const USERS_HREF = "/admin/utilisateurs";

type DetailTab = (typeof DETAIL_TABS)[number];
type T = ReturnType<typeof useTranslations<"roles">>;
type Data = AccessData;
type Role = Data["roles"][number];
type SortKey = "name" | "type" | "users" | "permissions" | "modified";

export function AccessOverview() {
  const t = useTranslations("roles");
  const { data } = useQuery({
    queryKey: ["access-overview"],
    queryFn: ({ signal }) => fetchAccessOverview(signal),
    staleTime: 60_000,
  });

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
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} onExport={onExport} />

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} />
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

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-3">
          <RoleTable
            t={t}
            rows={rows}
            selectedId={selectedId}
            onSelect={onSelect}
            sortKey={sortKey}
            sortDir={sortDir}
            onSort={onSort}
          />
          <div className="grid gap-3 xl:grid-cols-3">
            <TopRoles t={t} data={data} />
            <ByResource t={t} data={data} />
            <Pending t={t} data={data} />
          </div>
          <div className="grid gap-3 xl:grid-cols-2">
            <SodViolations t={t} data={data} />
            <Inactive t={t} data={data} />
          </div>
        </div>
        <DetailPanel
          t={t}
          role={selected}
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

function CompactKpi({ kpi, label }: { kpi: Data["kpis"][number]; label: string }) {
  return (
    <div className="flex h-[92px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <p className="truncate text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-[1.3rem] font-semibold leading-none text-white">{kpi.value}</p>
      <p className="mt-0.5 truncate text-[0.56rem] text-[var(--tessera-text-muted)]">{kpi.sub}</p>
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
  { key: "description" },
  { key: "users", sort: "users" },
  { key: "groups" },
  { key: "permissions", sort: "permissions" },
  { key: "scope" },
  { key: "environment" },
  { key: "modified", sort: "modified" },
  { key: "status" },
];

function RoleTable({
  t,
  rows,
  selectedId,
  onSelect,
  sortKey,
  sortDir,
  onSort,
}: {
  t: T;
  rows: Role[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  sortKey: SortKey | null;
  sortDir: "asc" | "desc";
  onSort: (key: SortKey) => void;
}) {
  return (
    <div
      data-testid="roles-table"
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
            {rows.map((r) => {
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
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="px-2 py-1.5 font-medium text-[var(--tessera-text)]">{r.name}</td>
                  <td className="px-2 py-1.5">
                    <Badge className={TYPE_BADGE[r.type]}>{t(`type.${r.type}`)}</Badge>
                  </td>
                  <td className="max-w-[220px] truncate px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {r.description}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text)]">{r.users}</td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.groups}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.permissions}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{r.scope}</td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{r.environment}</td>
                  <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    {r.modified}
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
                </tr>
              );
            })}
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length}
                  className="px-2 py-6 text-center text-[0.7rem] text-[var(--tessera-text-muted)]"
                >
                  {t("empty.roles")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>{t("footer.shown", { n: rows.length })}</span>
      </div>
    </div>
  );
}

// ── bottom panels ────────────────────────────────────────────────────────────

function TopRoles({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.top_roles.map((r) => r.value), 1);
  return (
    <Panel title={t("zone.topRoles")}>
      <ul className="flex flex-col gap-2">
        {data.top_roles.map((r) => (
          <li key={r.name} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-24 shrink-0 truncate text-[var(--tessera-text)]">{r.name}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
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
    <Panel title={t("zone.byResource")}>
      <ul className="flex flex-col gap-2">
        {data.access_by_resource.map((r) => (
          <li key={r.key} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-28 shrink-0 truncate text-[var(--tessera-text)]">
              {t(`resource.${r.key}`)}
            </span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
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
    <Panel title={t("zone.pending")}>
      {data.pending_requests.length === 0 ? (
        <EmptyHint>{t("empty.pending")}</EmptyHint>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.pending_requests.map((p) => (
            <li key={p.user} className="flex items-center gap-2 text-[0.66rem]">
              <span className="font-medium text-[var(--tessera-text)]">{p.user}</span>
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
                {p.role}
              </span>
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
    <Panel title={t("zone.sod")}>
      {data.sod_violations.length === 0 ? (
        <EmptyHint>{t("empty.sod")}</EmptyHint>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.sod_violations.map((v) => (
            <li key={v.user} className="flex items-center gap-2 text-[0.66rem]">
              <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-red-300" />
              <span className="font-medium text-[var(--tessera-text)]">{v.user}</span>
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
                {v.conflict}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Inactive({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.inactive")}>
      {data.inactive_accounts.length === 0 ? (
        <EmptyHint>{t("empty.inactive")}</EmptyHint>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {data.inactive_accounts.map((a) => (
            <li key={a.user} className="flex items-center gap-2 text-[0.66rem]">
              <span className="font-medium text-[var(--tessera-text)]">{a.user}</span>
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
                {a.role}
              </span>
              <span className="shrink-0 text-[var(--tessera-text-muted)]">{a.last_seen}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

function DetailPanel({
  t,
  role,
  tab,
  onTab,
  onClose,
}: {
  t: T;
  role: Role | null;
  tab: DetailTab;
  onTab: (tab: DetailTab) => void;
  onClose: () => void;
}) {
  if (!role) {
    return (
      <aside
        data-testid="role-detail"
        className="flex min-w-0 flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6 text-center xl:sticky xl:top-0 xl:h-fit xl:min-h-[200px]"
      >
        <Lock className="h-5 w-5 text-[var(--tessera-text-muted)]" />
        <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{t("detail.selectHint")}</p>
      </aside>
    );
  }
  const meta: [string, string][] = [
    [t("detail.scope"), role.scope],
    [t("detail.owner"), role.owner],
    [t("detail.modified"), role.modified],
    [t("detail.environment"), role.environment],
  ];
  return (
    <aside
      data-testid="role-detail"
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:sticky xl:top-0 xl:h-fit"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{role.name}</p>
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
            <Link href={USERS_HREF} className="text-[0.62rem] text-[#87bfff] hover:text-white">
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
                    <p className="truncate text-[var(--tessera-text)]">{m.name}</p>
                    <p className="truncate text-[0.56rem] text-[var(--tessera-text-muted)]">
                      {m.team}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0",
                      m.status === "active" ? "text-emerald-300" : "text-amber-300",
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
  children,
  className,
}: { title: string; children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <h3 className="mb-2 truncate text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {title}
      </h3>
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

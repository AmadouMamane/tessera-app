"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Download, Plus, Search, ShieldAlert, UploadCloud, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
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
const RISK_TEXT: Record<string, string> = {
  low: "text-emerald-300",
  medium: "text-amber-300",
  high: "text-red-300",
};
const DETAIL_TABS = ["overview", "permissions", "users", "groups", "history"] as const;

type T = ReturnType<typeof useTranslations<"roles">>;
type Data = AccessData;

export function AccessOverview() {
  const t = useTranslations("roles");
  const { data } = useQuery({
    queryKey: ["access-overview"],
    queryFn: ({ signal }) => fetchAccessOverview(signal),
    staleTime: 60_000,
  });

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} />

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} />
        ))}
      </div>

      <FilterStrip t={t} />

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-3">
          <RoleTable t={t} data={data} />
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
        <DetailPanel t={t} data={data} />
      </div>

      <Footer t={t} data={data} />
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({ t }: { t: T }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center justify-end gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <Button
        size="sm"
        variant="outline"
        className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
      >
        <Download className="h-4 w-4" /> {t("actions.export")}
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
      >
        <UploadCloud className="h-4 w-4" /> {t("actions.import")}
      </Button>
      <Button
        size="sm"
        className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
      >
        <Plus className="h-4 w-4" /> {t("actions.create")}
      </Button>
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

function FilterStrip({ t }: { t: T }) {
  const selects = ["type", "status", "environment"] as const;
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="relative min-w-[200px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          placeholder={t("filters.search")}
          className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none"
        />
      </div>
      {selects.map((s) => (
        <div
          key={s}
          className="flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)]"
        >
          {t(`filters.${s}`)} <ChevronRight className="h-3.5 w-3.5 rotate-90" />
        </div>
      ))}
    </section>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

function RoleTable({ t, data }: { t: T; data: Data }) {
  const cols = [
    "name",
    "type",
    "description",
    "users",
    "groups",
    "permissions",
    "scope",
    "environment",
    "modified",
    "status",
  ] as const;
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                  {t(`col.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.roles.map((r) => {
              const active = r.id === data.selected.id;
              return (
                <tr
                  key={r.id}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors hover:bg-[#0b2b49]",
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
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>
          1–{data.page_size} / {data.total_roles}
        </span>
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
            <span className="w-12 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
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
              {r.count} · {r.pct}%
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Pending({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.pending")}>
      <ul className="flex flex-col gap-1.5">
        {data.pending_requests.map((p) => (
          <li key={p.user} className="flex items-center gap-2 text-[0.66rem]">
            <span className="font-medium text-[var(--tessera-text)]">{p.user}</span>
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
              {p.role}
            </span>
            <span className="shrink-0 text-[var(--tessera-text-muted)]">{p.since}</span>
            <span className={cn("shrink-0 font-medium", RISK_TEXT[p.risk])}>
              {t(`risk.${p.risk}`)}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function SodViolations({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.sod")}>
      <ul className="flex flex-col gap-1.5">
        {data.sod_violations.map((v) => (
          <li key={v.user} className="flex items-center gap-2 text-[0.66rem]">
            <ShieldAlert className={cn("h-3.5 w-3.5 shrink-0", RISK_TEXT[v.severity])} />
            <span className="font-medium text-[var(--tessera-text)]">{v.user}</span>
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
              {v.conflict}
            </span>
            <span className={cn("shrink-0 font-medium", RISK_TEXT[v.severity])}>
              {t(`risk.${v.severity}`)}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Inactive({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.inactive")}>
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
    </Panel>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

function DetailPanel({ t, data }: { t: T; data: Data }) {
  const s = data.selected;
  const meta: [string, string][] = [
    [t("detail.scope"), s.scope],
    [t("detail.owner"), s.owner],
    [t("detail.created"), s.created],
    [t("detail.modified"), s.modified],
    [t("detail.environment"), s.environment],
  ];
  return (
    <aside className="flex min-w-0 flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:sticky xl:top-0 xl:h-fit">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">{s.name}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {s.id}
            </span>
            <Badge className={TYPE_BADGE[s.type]}>{t(`type.${s.type}`)}</Badge>
            <span
              className={cn("inline-flex items-center gap-1 text-[0.62rem]", STATUS_TEXT[s.status])}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> {t(`status.${s.status}`)}
            </span>
          </div>
        </div>
        <button
          type="button"
          aria-label="close"
          className="text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-[var(--tessera-border)] pb-2">
        {DETAIL_TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            className={cn(
              "rounded px-2 py-1 text-[0.62rem] font-medium",
              tab === "overview"
                ? "bg-[#0d3561] text-[#d8eaff]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
            )}
          >
            {t(`detailTabs.${tab}`)}
          </button>
        ))}
      </div>

      <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text)]">{s.description}</p>

      <dl className="flex flex-col gap-1 text-[0.66rem]">
        {meta.map(([k, v]) => (
          <KV key={k} label={k} value={v} />
        ))}
      </dl>

      <div className="border-t border-[var(--tessera-border)] pt-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <p className="text-[0.66rem] font-semibold text-[var(--tessera-text)]">
            {t("detail.members")} ({s.members.length})
          </p>
          <button type="button" className="text-[0.62rem] text-[#87bfff]">
            {t("detail.viewAll")} →
          </button>
        </div>
        <ul className="flex flex-col gap-1">
          {s.members.map((m) => (
            <li key={m.name} className="flex items-center gap-2 text-[0.66rem]">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-soft)] text-[0.56rem] font-semibold text-[var(--tessera-green)]">
                {m.name.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[var(--tessera-text)]">{m.name}</p>
                <p className="truncate text-[0.56rem] text-[var(--tessera-text-muted)]">{m.team}</p>
              </div>
              <span className="shrink-0 text-emerald-300">{t("status.active")}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-[var(--tessera-border)] pt-2">
        <Distribution
          title={t("detail.permDist")}
          items={s.permission_dist}
          labelOf={(k) => t(`perm.${k}`)}
        />
        <Distribution
          title={t("detail.accessScope")}
          items={s.access_scope}
          labelOf={(k) => t(`resource.${k}`)}
        />
      </div>
    </aside>
  );
}

function Distribution({
  title,
  items,
  labelOf,
}: {
  title: string;
  items: Data["selected"]["permission_dist"];
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

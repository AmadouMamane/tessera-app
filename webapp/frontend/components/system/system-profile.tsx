"use client";

import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronRight,
  Download,
  RefreshCcw,
  Server,
  TriangleAlert,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchSystemProfile } from "@/lib/api/client";
import type { SystemProfile as SystemData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const AUDIT_HREF = "/prouver/audit-logs";

type T = ReturnType<typeof useTranslations<"systemProfile">>;
type Data = SystemData;

/** ⓘ for a system KPI, reading systemProfile.explain.<k>; renders nothing where the
 * label is self-evident (no explain entry). */
function KpiInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("systemProfile.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

export function SystemProfile() {
  const t = useTranslations("systemProfile");
  const locale = useLocale();
  const { data, refetch, isFetching } = useQuery({
    queryKey: ["system-profile", locale],
    queryFn: ({ signal }) => fetchSystemProfile(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  const onExport = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "tessera-system-profile.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} onExport={onExport} onRefresh={() => refetch()} refreshing={isFetching} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        {data.kpis.map((kpi) => (
          <SystemKpi
            key={kpi.key}
            kpi={kpi}
            label={t(`kpi.${kpi.key}`)}
            info={<KpiInfo k={kpi.key} title={t(`kpi.${kpi.key}`)} />}
          />
        ))}
      </div>

      <div className="grid gap-3 xl:grid-cols-12">
        <Architecture t={t} data={data} className="xl:col-span-4" />
        <Topology t={t} data={data} className="xl:col-span-5" />
        <Resources t={t} data={data} className="xl:col-span-3" />
      </div>

      <div className="grid gap-3 xl:grid-cols-12">
        <OsInfo t={t} data={data} className="xl:col-span-4" />
        <Runtime t={t} data={data} className="xl:col-span-4" />
        <Health t={t} data={data} className="xl:col-span-4" />
      </div>

      <div className="grid gap-3 xl:grid-cols-12">
        <Services t={t} data={data} className="xl:col-span-5" />
        <Versions t={t} data={data} className="xl:col-span-3" />
        <Licenses t={t} data={data} className="xl:col-span-4" />
      </div>

      <Footer t={t} data={data} />
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({
  t,
  onExport,
  onRefresh,
  refreshing,
}: { t: T; onExport: () => void; onRefresh: () => void; refreshing: boolean }) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="inline-flex items-center gap-1.5 text-[0.72rem] font-medium text-[var(--tessera-text)]">
        <Server className="h-4 w-4 text-[var(--tessera-fg-info)]" /> {t("subtitle")}
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
        <Button
          size="sm"
          variant="outline"
          onClick={onRefresh}
          disabled={refreshing}
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <RefreshCcw className={cn("h-4 w-4", refreshing && "animate-spin")} />{" "}
          {t("actions.refresh")}
        </Button>
      </div>
    </section>
  );
}

function SystemKpi({
  kpi,
  label,
  info,
}: { kpi: Data["kpis"][number]; label: string; info?: ReactNode }) {
  return (
    <div className="flex h-[104px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 text-[0.66rem] font-medium text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
      </p>
      {kpi.kind === "status" ? (
        <div className="mt-1 flex items-center gap-1.5">
          <CheckCircle2 className="h-4 w-4 text-[var(--tessera-fg-success)]" />
          <span className="text-[0.95rem] font-semibold text-[var(--tessera-fg-success)]">
            {kpi.value}
          </span>
        </div>
      ) : (
        <div className="mt-1 flex items-center gap-2">
          <span className="text-[1.25rem] font-semibold leading-tight text-[var(--tessera-text-strong)]">
            {kpi.value}
          </span>
          {kpi.delta ? (
            <span className="text-[0.62rem] font-medium text-[var(--tessera-fg-success)]">
              {kpi.delta}
            </span>
          ) : null}
        </div>
      )}
      <Truncate as="p" className="mt-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]">
        {kpi.sub}
      </Truncate>
      {kpi.kind === "chart" ? (
        <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
      ) : (
        <div className="mt-auto">
          {kpi.link ? (
            <span className="text-[0.6rem] text-[var(--tessera-fg-info)]">{kpi.link} →</span>
          ) : kpi.extra ? (
            <span className="text-[0.58rem] text-[var(--tessera-text-muted)]">{kpi.extra}</span>
          ) : null}
        </div>
      )}
    </div>
  );
}

// ── zones ────────────────────────────────────────────────────────────────────

function Architecture({ t, data, className }: { t: T; data: Data; className?: string }) {
  const a = data.architecture;
  const rows: [string, string][] = [
    [t("arch.edition"), a.edition],
    [t("arch.version"), a.version],
    [t("arch.deployment"), a.deployment],
    [t("arch.region"), a.region],
    [t("arch.cluster"), a.cluster],
    [t("arch.deployed"), a.deployed_at],
    [t("arch.uptime"), a.uptime],
    [t("arch.nextMaintenance"), a.next_maintenance],
  ];
  return (
    <Panel title={t("zone.architecture")} className={className}>
      <dl className="flex flex-col gap-1.5 text-[0.7rem]">
        {rows.map(([k, v]) => (
          <KV key={k} label={k} value={v} />
        ))}
      </dl>
    </Panel>
  );
}

function Topology({ t, data, className }: { t: T; data: Data; className?: string }) {
  const tp = data.topology;
  return (
    <Panel title={t("zone.topology")} className={className}>
      <div className="flex flex-col items-center gap-1.5">
        <Row nodes={tp.tiers} />
        <Connector />
        <Row nodes={tp.planes} />
        <Connector />
        <div className="grid w-full grid-cols-3 gap-1.5">
          {tp.stores.map((s) => (
            <div
              key={s.key}
              className="flex flex-col items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-center"
            >
              <span className="text-[0.66rem] font-medium text-[var(--tessera-text)]">
                {s.label}
              </span>
              <span className="text-[0.54rem] text-[var(--tessera-text-muted)]">{s.detail}</span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function Row({ nodes }: { nodes: { key: string; label: string; nodes: number }[] }) {
  return (
    <div
      className="grid w-full gap-1.5"
      style={{ gridTemplateColumns: `repeat(${nodes.length}, minmax(0, 1fr))` }}
    >
      {nodes.map((n) => (
        <div
          key={n.key}
          className="flex items-center justify-center gap-1.5 rounded-md border border-[#2e72d2]/40 bg-[#0d3561]/40 px-2 py-1.5 text-center"
        >
          <span className="text-[0.68rem] font-medium text-[var(--tessera-fg-info)]">
            {n.label}
          </span>
          <span className="rounded bg-[var(--tessera-bg)] px-1 text-[0.54rem] tabular-nums text-[var(--tessera-text-muted)]">
            ×{n.nodes}
          </span>
        </div>
      ))}
    </div>
  );
}

function Connector() {
  return <span className="h-2 w-px bg-[var(--tessera-border)]" />;
}

function Resources({ t, data, className }: { t: T; data: Data; className?: string }) {
  const r = data.resources;
  const sum = r.slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 42;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <Panel title={t("zone.resources")} className={className}>
      <div className="flex items-center gap-3">
        <div className="relative h-[112px] w-[112px] shrink-0">
          <svg viewBox="0 0 112 112" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle
              cx="56"
              cy="56"
              r={R}
              fill="none"
              stroke="var(--tessera-border)"
              strokeWidth="9"
            />
            {r.slices.map((s) => {
              const frac = s.count / sum;
              const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
              off += frac;
              return (
                <circle
                  key={s.key}
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
          <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden text-center">
            <span className="line-clamp-2 max-w-[54px] break-words text-[0.62rem] uppercase leading-tight text-[var(--tessera-text-muted)]">
              Total
            </span>
            <span className="max-w-[44px] truncate text-[0.78rem] font-semibold leading-none text-[var(--tessera-text-strong)]">
              {r.total}
            </span>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.64rem]">
          {r.slices.map((s) => (
            <li key={s.key} className="flex flex-col gap-0.5">
              <span className="flex min-w-0 items-center gap-1">
                <span
                  className="h-1.5 w-1.5 shrink-0 rounded-full"
                  style={{ background: s.color }}
                />
                <span className="min-w-0 truncate text-[var(--tessera-text)]">
                  {t(`res.${s.key}`)}
                </span>
              </span>
              <span className="pl-2.5 tabular-nums text-[var(--tessera-text-muted)]">
                {s.count} · {s.pct}%
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function OsInfo({ t, data, className }: { t: T; data: Data; className?: string }) {
  const o = data.os_info;
  const rows: [string, string][] = [
    [t("os.os"), o.os],
    [t("os.kernel"), o.kernel],
    [t("os.arch"), o.arch],
    [t("os.virtualization"), o.virtualization],
    [t("os.cpu"), o.cpu],
    [t("os.memory"), o.memory],
    [t("os.systemTime"), o.system_time],
    [t("os.timezone"), o.timezone],
    [t("os.fqdn"), o.fqdn],
    [t("os.infraId"), o.infra_id],
    [t("os.support"), o.support],
  ];
  return (
    <Panel title={t("zone.os")} className={className}>
      <dl className="flex flex-col gap-1 text-[0.66rem]">
        {rows.map(([k, v]) => (
          <KV key={k} label={k} value={v} mono />
        ))}
      </dl>
    </Panel>
  );
}

function Runtime({ t, data, className }: { t: T; data: Data; className?: string }) {
  const r = data.runtime;
  const rows: [string, string][] = [
    [t("runtime.uptime"), r.uptime],
    [t("runtime.started"), r.started],
    [t("runtime.auditLines"), r.audit_lines],
    [t("runtime.auditChain"), r.audit_chain],
  ];
  return (
    <Panel
      title={t("zone.runtime")}
      className={className}
      action={<ViewAll label={t("runtime.viewAudit")} href={AUDIT_HREF} />}
    >
      <dl className="flex flex-col gap-1.5 text-[0.7rem]">
        {rows.map(([k, v]) => (
          <KV key={k} label={k} value={v} />
        ))}
      </dl>
    </Panel>
  );
}

function Health({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("zone.health")}
      className={className}
      action={<ViewAll label={t("health.viewAll")} href={AUDIT_HREF} />}
    >
      <ul className="grid grid-cols-1 gap-1 sm:grid-cols-2">
        {data.health_checks.map((h) => (
          <li
            key={h.key}
            className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.66rem]"
          >
            <span className="min-w-0 truncate text-[var(--tessera-text)]">
              {t(`health.${h.key}`)}
            </span>
            {h.status === "ok" ? (
              <span className="inline-flex items-center gap-1 text-[var(--tessera-fg-success)]">
                <CheckCircle2 className="h-3 w-3" /> {t("status.ok")}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[var(--tessera-fg-warning)]">
                <TriangleAlert className="h-3 w-3" /> {t("status.warn")}
              </span>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Services({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel title={t("zone.services")} className={className}>
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("svcCol.name")}</th>
            <th className="px-1.5 py-1 font-medium">{t("svcCol.status")}</th>
            <th className="px-1.5 py-1 font-medium">{t("svcCol.version")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("svcCol.instances")}</th>
          </tr>
        </thead>
        <tbody>
          {data.services.map((s) => (
            <tr key={s.name} className="border-b border-[var(--tessera-border)]/60 last:border-0">
              <td className="px-1.5 py-1 text-[var(--tessera-text)]">{s.name}</td>
              <td className="px-1.5 py-1">
                {s.status === "ok" ? (
                  <span className="inline-flex items-center gap-1 text-[var(--tessera-fg-success)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> {t("status.ok")}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[var(--tessera-fg-warning)]">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-400" /> {t("status.warn")}
                  </span>
                )}
              </td>
              <td className="px-1.5 py-1 font-mono text-[0.64rem] text-[var(--tessera-text-muted)]">
                {s.version}
              </td>
              <td className="px-1.5 py-1 text-right tabular-nums text-[var(--tessera-text-muted)]">
                {s.instances}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Versions({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel title={t("zone.versions")} className={className}>
      <dl className="flex flex-col gap-1.5 text-[0.68rem]">
        {data.versions.map((v) => (
          <div key={v.name} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text)]">{v.name}</dt>
            <dd className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {v.version}
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function Licenses({ t, data, className }: { t: T; data: Data; className?: string }) {
  const l = data.licenses;
  const rows: [string, string][] = [
    [t("lic.edition"), l.edition],
    [t("lic.seats"), l.seats],
    [t("lic.expiry"), l.expiry],
    [t("lic.quotaCalls"), l.quota_calls],
    [t("lic.quotaStorage"), l.quota_storage],
  ];
  return (
    <Panel title={t("zone.licenses")} className={className}>
      <dl className="flex flex-col gap-1.5 text-[0.7rem]">
        {rows.map(([k, v]) => (
          <KV key={k} label={k} value={v} />
        ))}
      </dl>
    </Panel>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Panel({
  title,
  action,
  children,
  className,
}: {
  title: string;
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
        <h3 className="min-w-0 truncate text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
          {title}
        </h3>
        {action}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd
        className={cn(
          "min-w-0 truncate text-right text-[var(--tessera-text)]",
          mono && "font-mono text-[0.62rem]",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function ViewAll({ label, href }: { label: string; href: typeof AUDIT_HREF }) {
  return (
    <Link
      href={href}
      className="flex shrink-0 items-center gap-0.5 text-[0.64rem] font-medium text-[var(--tessera-fg-info)] hover:text-[var(--tessera-fg-info)]"
    >
      {label} <ChevronRight className="h-3 w-3" />
    </Link>
  );
}

function Footer({ t, data }: { t: T; data: Data }) {
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span className="flex items-center gap-1.5">
        <Server className="h-3.5 w-3.5" /> {t("footer.version", { v: data.footer.version })}
      </span>
      <span>{t("footer.source", { src: data.footer.source })}</span>
    </footer>
  );
}

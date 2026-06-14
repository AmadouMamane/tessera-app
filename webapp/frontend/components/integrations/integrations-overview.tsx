"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Plug, Plus, Search, UploadCloud, X, Zap } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { fetchIntegrationsOverview } from "@/lib/api/client";
import type { IntegrationsOverview as IntegrationsData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const STATUS: Record<"active" | "warning" | "error" | "disabled", { dot: string; text: string }> = {
  active: { dot: "bg-emerald-400", text: "text-emerald-300" },
  warning: { dot: "bg-amber-400", text: "text-amber-300" },
  error: { dot: "bg-red-400", text: "text-red-300" },
  disabled: { dot: "bg-[var(--tessera-text-muted)]", text: "text-[var(--tessera-text-muted)]" },
};
const CRIT_BADGE: Record<string, string> = {
  low: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  medium: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  high: "border-red-500/30 bg-red-500/15 text-red-300",
};
const DETAIL_TABS = [
  "config",
  "endpoints",
  "secrets",
  "mappings",
  "policies",
  "calls",
  "history",
] as const;

type T = ReturnType<typeof useTranslations<"integrations">>;
type Data = IntegrationsData;

export function IntegrationsOverview() {
  const t = useTranslations("integrations");
  const { data } = useQuery({
    queryKey: ["integrations-overview"],
    queryFn: ({ signal }) => fetchIntegrationsOverview(signal),
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

      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} />
        ))}
      </div>

      <FilterStrip t={t} />

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex min-w-0 flex-col gap-3">
          <IntegrationTable t={t} data={data} />
          <div className="grid gap-3 xl:grid-cols-3">
            <ByType t={t} data={data} />
            <ByEnv t={t} data={data} />
            <Top t={t} data={data} />
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
        <Zap className="h-4 w-4" /> {t("actions.test")}
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
      <p className="mt-0.5 text-[1.2rem] font-semibold leading-none text-white">{kpi.value}</p>
      <p className="mt-0.5 truncate text-[0.56rem] text-[var(--tessera-text-muted)]">{kpi.sub}</p>
      <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
    </div>
  );
}

function FilterStrip({ t }: { t: T }) {
  const selects = ["status", "type", "environment", "owner"] as const;
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

function IntegrationTable({ t, data }: { t: T; data: Data }) {
  const cols = [
    "name",
    "type",
    "status",
    "environment",
    "owner",
    "calls",
    "successRate",
    "responseTime",
    "lastSync",
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
            {data.integrations.map((i) => {
              const active = i.id === data.selected.id;
              return (
                <tr
                  key={i.id}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors hover:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="px-2 py-1.5">
                    <span className="inline-flex items-center gap-1.5 text-[var(--tessera-text)]">
                      <Plug className="h-3 w-3 text-[#87bfff]" /> {i.name}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {t(`type.${i.type}`)}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className={cn("inline-flex items-center gap-1", STATUS[i.status].text)}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[i.status].dot)} />{" "}
                      {t(`status.${i.status}`)}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-emerald-300">{i.environment}</td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{i.owner}</td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text)]">{i.calls}</td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {i.success_rate}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {i.response_time}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    {i.last_sync}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>
          1–{data.page_size} / {data.total_integrations}
        </span>
      </div>
    </div>
  );
}

// ── bottom charts ────────────────────────────────────────────────────────────

function ByType({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.byType")}>
      <Donut slices={data.by_type} total={data.by_type_total} labelOf={(k) => t(`type.${k}`)} />
    </Panel>
  );
}

function ByEnv({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.byEnv")}>
      <ul className="flex flex-col gap-2">
        {data.by_env.map((e) => (
          <li key={e.key} className="flex flex-col gap-0.5 text-[0.66rem]">
            <div className="flex items-center justify-between gap-1.5">
              <span className="text-[var(--tessera-text)]">{t(`env.${e.key}`)}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">
                {e.value} · {e.pct}%
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

function Top({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.top_integrations.map((i) => i.value), 1);
  return (
    <Panel title={t("zone.top")}>
      <ul className="flex flex-col gap-2">
        {data.top_integrations.map((i) => (
          <li key={i.name} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-24 shrink-0 truncate text-[var(--tessera-text)]">{i.name}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full bg-[#2e72d2]"
                style={{ width: `${(i.value / max) * 100}%` }}
              />
            </div>
            <span className="w-12 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {i.label}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

function DetailPanel({ t, data }: { t: T; data: Data }) {
  const s = data.selected;
  const config: [string, string][] = [
    [t("detail.url"), s.config.url],
    [t("detail.version"), s.config.version],
    [t("detail.auth"), s.config.auth],
    [t("detail.timeout"), s.config.timeout],
    [t("detail.retry"), s.config.retry],
    [t("detail.rateLimit"), s.config.rate_limit],
    [t("detail.pagination"), s.config.pagination],
  ];
  const security: [string, string][] = [
    [t("detail.method"), s.security.method],
    [t("detail.clientId"), s.security.client_id],
    [t("detail.cert"), s.security.cert],
    [t("detail.keyRotation"), s.security.key_rotation],
    [t("detail.lastRotation"), s.security.last_rotation],
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
            <span
              className={cn("inline-flex items-center gap-1 text-[0.62rem]", STATUS[s.status].text)}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[s.status].dot)} />{" "}
              {t(`status.${s.status}`)}
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
              "rounded px-2 py-1 text-[0.6rem] font-medium",
              tab === "config"
                ? "bg-[#0d3561] text-[#d8eaff]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
            )}
          >
            {t(`detailTabs.${tab}`)}
          </button>
        ))}
      </div>

      <Section title={t("detail.connectivity")}>
        <div className="grid grid-cols-3 gap-2 text-center">
          <Stat label={t("detail.responseTime")} value={s.response_time} />
          <Stat label={t("detail.successRate")} value={s.success_rate} tone="text-emerald-300" />
          <Stat label={t("detail.lastSync")} value={s.last_sync} small />
        </div>
        <Button
          size="sm"
          variant="outline"
          className="mt-2 h-7 w-full justify-center gap-1.5 border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[0.66rem]"
        >
          <Zap className="h-3.5 w-3.5" /> {t("actions.test")}
        </Button>
      </Section>

      <Section title={t("detail.general")}>
        <p className="mb-1.5 text-[0.7rem] leading-relaxed text-[var(--tessera-text)]">
          {s.description}
        </p>
        <dl className="flex flex-col gap-1 text-[0.66rem]">
          <KV label={t("detail.owner")} value={s.owner} />
          <KV label={t("detail.environment")} value={s.environment} />
          <KV label={t("detail.region")} value={s.region} />
          <div className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{t("detail.criticality")}</dt>
            <dd>
              <Badge className={CRIT_BADGE[s.criticality]}>
                {t(`criticality.${s.criticality}`)}
              </Badge>
            </dd>
          </div>
        </dl>
      </Section>

      <Section title={t("detail.usage")}>
        <div className="grid grid-cols-3 gap-2">
          {(
            [
              ["read", s.usage.read],
              ["write", s.usage.write],
              ["cost", s.usage.cost],
            ] as const
          ).map(([k, m]) => (
            <div
              key={k}
              className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2"
            >
              <p className="truncate text-[0.56rem] text-[var(--tessera-text-muted)]">
                {t(`detail.${k}`)}
              </p>
              <p className="text-[0.82rem] font-semibold text-white">{m.value}</p>
              <p className="text-[0.56rem] text-emerald-300">{m.delta}</p>
            </div>
          ))}
        </div>
      </Section>

      <div className="grid grid-cols-1 gap-3">
        <Section title={t("detail.config")}>
          <dl className="flex flex-col gap-1 text-[0.64rem]">
            {config.map(([k, v]) => (
              <KV key={k} label={k} value={v} mono />
            ))}
          </dl>
        </Section>
        <Section title={t("detail.security")}>
          <dl className="flex flex-col gap-1 text-[0.64rem]">
            {security.map(([k, v]) => (
              <KV key={k} label={k} value={v} mono />
            ))}
          </dl>
        </Section>
      </div>
    </aside>
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

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)]/40 p-2.5">
      <p className="mb-1.5 text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {title}
      </p>
      {children}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  small,
}: { label: string; value: string; tone?: string; small?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="truncate text-[0.54rem] text-[var(--tessera-text-muted)]">{label}</p>
      <p
        className={cn(
          "truncate font-semibold text-white",
          small ? "text-[0.62rem]" : "text-[0.82rem]",
          tone,
        )}
      >
        {value}
      </p>
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
              {s.count} · {s.pct}%
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

function Footer({ t, data }: { t: T; data: Data }) {
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <span>{t("footer.total", { n: data.footer.total })}</span>
      <span>{t("footer.source", { src: data.footer.source })}</span>
    </footer>
  );
}

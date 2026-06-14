"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Link2, Plus, Search, UploadCloud, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { fetchSourcesOverview } from "@/lib/api/client";
import type { SourcesOverview as SourcesData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const CLASS_BADGE: Record<string, string> = {
  public: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  internal: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  confidential: "border-violet-500/30 bg-violet-500/15 text-violet-300",
};
const STATUS_TEXT: Record<string, string> = {
  active: "text-emerald-300",
  deprecated: "text-amber-300",
  disabled: "text-[var(--tessera-text-muted)]",
};
const STATUS_DOT: Record<string, string> = {
  active: "bg-emerald-400",
  deprecated: "bg-amber-400",
  disabled: "bg-[var(--tessera-text-muted)]",
};
const DETAIL_TABS = [
  "overview",
  "details",
  "schema",
  "access",
  "activity",
  "dependencies",
  "history",
] as const;

type T = ReturnType<typeof useTranslations<"sources">>;
type Data = SourcesData;

export function SourcesOverview() {
  const t = useTranslations("sources");
  const { data } = useQuery({
    queryKey: ["sources-overview"],
    queryFn: ({ signal }) => fetchSourcesOverview(signal),
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

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col gap-3">
          <SourceTable t={t} data={data} />
          <div className="grid gap-3 xl:grid-cols-3">
            <ByType t={t} data={data} />
            <ByEnv t={t} data={data} />
            <CostBySource t={t} data={data} />
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
        <UploadCloud className="h-4 w-4" /> {t("actions.importSource")}
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
      >
        <Link2 className="h-4 w-4" /> {t("actions.connectSource")}
      </Button>
      <Button
        size="sm"
        className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
      >
        <Plus className="h-4 w-4" /> {t("actions.createSource")}
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
      <p className="mt-0.5 text-[1.25rem] font-semibold leading-none text-white">{kpi.value}</p>
      <p className="mt-0.5 truncate text-[0.56rem] text-[var(--tessera-text-muted)]">{kpi.sub}</p>
      <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
    </div>
  );
}

function FilterStrip({ t }: { t: T }) {
  const selects = ["status", "type", "classification", "environment", "owner"] as const;
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="relative min-w-[180px] flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
        <input
          type="search"
          placeholder={t("filters.snapshot")}
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

function SourceTable({ t, data }: { t: T; data: Data }) {
  const cols = [
    "name",
    "type",
    "classification",
    "environment",
    "status",
    "dataTotal",
    "indexed",
    "lastSync",
    "quality",
    "freshness",
    "owner",
    "cost",
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
            {data.sources.map((s) => {
              const active = s.id === data.selected.id;
              return (
                <tr
                  key={s.id}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors hover:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="px-2 py-1.5">
                    <span className="text-[var(--tessera-text)]">{s.name}</span>
                    <span className="ml-1.5 font-mono text-[0.56rem] text-[var(--tessera-text-muted)]">
                      {s.id}
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
                  <td className="px-2 py-1.5 text-emerald-300">{s.environment}</td>
                  <td className="px-2 py-1.5">
                    <span className={cn("inline-flex items-center gap-1", STATUS_TEXT[s.status])}>
                      <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[s.status])} />{" "}
                      {t(`status.${s.status}`)}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text)]">
                    {s.data_total}
                  </td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {s.indexed}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    {s.last_sync}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="tabular-nums text-[var(--tessera-text-muted)]">
                      {s.quality}%
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{s.freshness}</td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{s.owner}</td>
                  <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {s.cost}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>
          1–{data.page_size} / {data.total_sources}
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

function CostBySource({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.cost_by_source.map((c) => c.value), 1);
  return (
    <Panel title={t("zone.costBySource")}>
      <ul className="flex flex-col gap-2">
        {data.cost_by_source.map((c) => (
          <li key={c.name} className="flex items-center gap-2 text-[0.66rem]">
            <span className="w-24 shrink-0 truncate text-[var(--tessera-text)]">{c.name}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full bg-[#2e72d2]"
                style={{ width: `${(c.value / max) * 100}%` }}
              />
            </div>
            <span className="w-10 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {c.label}
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
  const meta: [string, string][] = [
    [t("col.type"), t(`type.${s.type}`)],
    [t("detail.connector"), s.connector],
    [t("detail.environment"), s.environment],
    [t("detail.region"), s.region],
    [t("detail.classification"), t(`classification.${s.classification}`)],
    [t("detail.owner"), s.owner],
    [t("detail.created"), s.created],
    [t("detail.modified"), s.modified],
    [t("detail.retention"), s.retention],
    [t("detail.source"), s.source],
  ];
  const metrics: [string, { value: string; delta: string }][] = [
    [t("detail.documents"), s.documents],
    [t("detail.queries"), s.queries],
    [t("detail.cost"), s.cost],
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
              className={cn("inline-flex items-center gap-1 text-[0.62rem]", STATUS_TEXT[s.status])}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[s.status])} />{" "}
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

      <div className="grid grid-cols-2 gap-3">
        <dl className="flex flex-col gap-1 text-[0.66rem]">
          {meta.map(([k, v]) => (
            <KV key={k} label={k} value={v} />
          ))}
        </dl>
        <dl className="flex flex-col gap-1.5 text-[0.66rem]">
          <div>
            <p className="text-[var(--tessera-text-muted)]">{t("detail.usage")}</p>
            <p className="text-sm font-semibold text-white">{s.usage}</p>
          </div>
          {metrics.map(([k, m]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <dt className="text-[var(--tessera-text-muted)]">{k}</dt>
              <dd className="flex items-baseline gap-1">
                <span className="tabular-nums text-[var(--tessera-text)]">{m.value}</span>
                <span className="text-[0.58rem] text-emerald-300">{m.delta}</span>
              </dd>
            </div>
          ))}
        </dl>
      </div>

      <div className="flex flex-wrap gap-1">
        {s.tags.map((tag) => (
          <span
            key={tag}
            className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]"
          >
            {tag}
          </span>
        ))}
      </div>

      <div className="border-t border-[var(--tessera-border)] pt-2">
        <div className="mb-1 flex items-center justify-between gap-2">
          <p className="text-[0.66rem] font-semibold text-[var(--tessera-text)]">
            {t("detail.qualityTitle")}
          </p>
          <button type="button" className="text-[0.62rem] text-[#87bfff]">
            {t("detail.viewDetail")} →
          </button>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative h-[72px] w-[72px] shrink-0">
            <Ring
              slices={s.quality_breakdown.map((q) => ({ pct: q.pct, color: q.color }))}
              center={`${s.quality_global}%`}
              caption={t("detail.scoreGlobal")}
            />
          </div>
          <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.64rem]">
            {s.quality_breakdown.map((q) => (
              <li key={q.key} className="flex items-center gap-1.5">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: q.color }} />
                <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                  {t(`quality.${q.key}`)}
                </span>
                <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                  {q.pct}%
                </span>
              </li>
            ))}
          </ul>
        </div>
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
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
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

function Ring({
  slices,
  center,
  caption,
}: { slices: { pct: number; color: string }[]; center: string; caption: string }) {
  const R = 26;
  const C = 2 * Math.PI * R;
  const total = slices.reduce((s, x) => s + x.pct, 0) || 1;
  let off = 0;
  return (
    <>
      <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="32" cy="32" r={R} fill="none" stroke="var(--tessera-border)" strokeWidth="7" />
        {slices.map((s, i) => {
          const frac = s.pct / total;
          const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
          off += frac;
          return (
            <circle
              key={`${i}-${s.color}`}
              cx="32"
              cy="32"
              r={R}
              fill="none"
              stroke={s.color}
              strokeWidth="7"
              strokeDasharray={`${seg.dash} ${seg.gap}`}
              strokeDashoffset={seg.o}
            />
          );
        })}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-sm font-semibold tabular-nums text-white">{center}</span>
        <span className="px-1 text-[0.4rem] uppercase leading-tight text-[var(--tessera-text-muted)]">
          {caption}
        </span>
      </div>
    </>
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

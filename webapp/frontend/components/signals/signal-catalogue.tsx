"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Download, FileSearch, Plus, Search, UploadCloud, X } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { StretchChart } from "@/components/cockpit/stretch-chart";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { fetchSignalCatalogue } from "@/lib/api/client";
import type { SignalCatalogue as SignalData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const SEV_BADGE: Record<string, string> = {
  critical: "border-red-500/30 bg-red-500/15 text-red-300",
  high: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  medium: "border-yellow-500/30 bg-yellow-500/15 text-yellow-300",
  low: "border-sky-500/30 bg-sky-500/15 text-sky-300",
};
const STATUS_BADGE: Record<string, string> = {
  active: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  evaluation: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  deprecated: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  disabled:
    "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
};
const DETAIL_TABS = ["overview", "definition", "performance", "history", "dependencies"] as const;

type T = ReturnType<typeof useTranslations<"signalCatalogue">>;
type Data = SignalData;

export function SignalCatalogue() {
  const t = useTranslations("signalCatalogue");
  const { data } = useQuery({
    queryKey: ["signal-catalogue"],
    queryFn: ({ signal }) => fetchSignalCatalogue(signal),
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

      <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 xl:grid-cols-9">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} />
        ))}
      </div>

      <FilterStrip t={t} data={data} />

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_360px]">
        <SignalTable t={t} data={data} />
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
        <UploadCloud className="h-4 w-4" /> {t("actions.importSignal")}
      </Button>
      <Button
        size="sm"
        variant="outline"
        className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
      >
        <Download className="h-4 w-4" /> {t("actions.exportCatalogue")}
      </Button>
      <Button
        size="sm"
        className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
      >
        <Plus className="h-4 w-4" /> {t("actions.createSignal")}
      </Button>
    </section>
  );
}

function CompactKpi({ kpi, label }: { kpi: Data["kpis"][number]; label: string }) {
  return (
    <div className="flex h-[88px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <p className="truncate text-[0.62rem] font-medium text-[var(--tessera-text-muted)]">
        {label}
      </p>
      <p className="mt-0.5 text-[1.3rem] font-semibold leading-none text-white">{kpi.value}</p>
      <p className="mt-0.5 truncate text-[0.56rem] text-[var(--tessera-text-muted)]">{kpi.sub}</p>
      <MetricSparkline className="mt-auto h-4 w-full" values={kpi.series} tone="success" />
    </div>
  );
}

function FilterStrip({ t, data }: { t: T; data: Data }) {
  const selects = ["status", "severity", "category", "source", "owner", "environment"] as const;
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
      <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
        {data.total_signals} {t("footer.total", { n: "" }).replace(/\d+\s*/, "")}
      </span>
    </section>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

function SignalTable({ t, data }: { t: T; data: Data }) {
  const cols = [
    "name",
    "category",
    "description",
    "source",
    "severity",
    "status",
    "quality",
    "lastActivity",
    "owner",
    "modified",
  ] as const;
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-[var(--tessera-surface)]">
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2.5 py-2 font-medium">
                  {t(`col.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.signals.map((sig) => {
              const active = sig.id === data.selected.id;
              return (
                <tr
                  key={sig.id}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors hover:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="px-2.5 py-2">
                    <span className="font-mono text-[0.7rem] text-[var(--tessera-text)]">
                      {sig.name}
                    </span>
                    <span className="ml-1.5 font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                      {sig.id}
                    </span>
                  </td>
                  <td className="px-2.5 py-2">
                    <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                      {t(`category.${sig.category}`)}
                    </Badge>
                  </td>
                  <td className="max-w-[220px] truncate px-2.5 py-2 text-[var(--tessera-text-muted)]">
                    {sig.description}
                  </td>
                  <td className="px-2.5 py-2 text-[var(--tessera-text-muted)]">{sig.source}</td>
                  <td className="px-2.5 py-2">
                    <Badge className={SEV_BADGE[sig.severity]}>
                      {t(`severity.${sig.severity}`)}
                    </Badge>
                  </td>
                  <td className="px-2.5 py-2">
                    <Badge className={STATUS_BADGE[sig.status]}>{t(`status.${sig.status}`)}</Badge>
                  </td>
                  <td className="px-2.5 py-2">
                    <div className="flex items-center gap-1.5">
                      <div className="h-1.5 w-10 rounded-full bg-[var(--tessera-bg)]">
                        <div
                          className={cn(
                            "h-full rounded-full",
                            sig.quality >= 90
                              ? "bg-emerald-400"
                              : sig.quality >= 75
                                ? "bg-amber-400"
                                : "bg-red-400",
                          )}
                          style={{ width: `${sig.quality}%` }}
                        />
                      </div>
                      <span className="tabular-nums text-[var(--tessera-text-muted)]">
                        {sig.quality}%
                      </span>
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-2.5 py-2 text-[var(--tessera-text-muted)]">
                    {sig.last_activity}
                  </td>
                  <td className="px-2.5 py-2 text-[var(--tessera-text-muted)]">{sig.owner}</td>
                  <td className="whitespace-nowrap px-2.5 py-2 font-mono text-[0.66rem] text-[var(--tessera-text-muted)]">
                    {sig.modified}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>
          1–{data.page_size} / {data.total_signals}
        </span>
        <div className="flex items-center gap-1">
          {[1, 2, 3, "…", 32].map((p, i) => (
            <button
              key={`${p}-${i}`}
              type="button"
              className={cn(
                "h-6 min-w-6 rounded px-1.5 text-[0.66rem]",
                p === 1
                  ? "bg-[#0d3561] text-[#d8eaff]"
                  : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── detail panel ─────────────────────────────────────────────────────────────

function DetailPanel({ t, data }: { t: T; data: Data }) {
  const s = data.selected;
  const maxDist = Math.max(...s.distribution.map((d) => d.count), 1);
  const meta: [string, string][] = [
    [t("detail.source"), s.source],
    [t("detail.type"), s.type],
    [t("detail.unit"), s.unit],
    [t("detail.direction"), s.direction],
    [t("detail.frequency"), s.frequency],
    [t("detail.environment"), s.environment],
  ];
  const thresholds: [string, string][] = [
    [t("detail.severity"), s.severity],
    [t("detail.thresholdCritical"), s.threshold_critical],
    [t("detail.thresholdAlert"), s.threshold_alert],
    [t("detail.model"), s.model],
    [t("detail.lastActivity"), s.last_activity],
    [t("detail.quality"), `${s.quality}%`],
  ];
  return (
    <aside className="flex min-w-0 flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:sticky xl:top-0 xl:h-fit">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-mono text-sm font-semibold text-white">{s.name}</p>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <span className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {s.id}
            </span>
            <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
              {t(`category.${s.category}`)}
            </Badge>
            <Badge className={STATUS_BADGE[s.status]}>{t(`status.${s.status}`)}</Badge>
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
              "rounded px-2 py-1 text-[0.66rem] font-medium",
              tab === "overview"
                ? "bg-[#0d3561] text-[#d8eaff]"
                : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]",
            )}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>

      <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text)]">{s.description}</p>

      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        <dl className="flex flex-col gap-1 text-[0.66rem]">
          {meta.map(([k, v]) => (
            <KV key={k} label={k} value={v} />
          ))}
        </dl>
        <dl className="flex flex-col gap-1 text-[0.66rem]">
          {thresholds.map(([k, v]) => (
            <KV key={k} label={k} value={v} />
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

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="mb-1 text-[0.62rem] font-semibold text-[var(--tessera-text)]">
            {t("detail.distribution")}
          </p>
          <div className="flex h-[70px] items-end gap-1">
            {s.distribution.map((d) => (
              <div key={d.label} className="flex flex-1 flex-col items-center gap-0.5">
                <div
                  className="w-full rounded-t-sm"
                  style={{ height: `${(d.count / maxDist) * 100}%`, background: d.color }}
                />
                <span className="text-[0.46rem] text-[var(--tessera-text-muted)]">{d.label}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-1 text-[0.62rem] font-semibold text-[var(--tessera-text)]">
            {t("detail.trend")}
          </p>
          <div className="h-[70px]">
            <StretchChart
              title={t("detail.trend")}
              lines={[{ points: s.trend, color: "#34d399" }]}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 border-t border-[var(--tessera-border)] pt-2">
        <div>
          <p className="mb-1 text-[0.62rem] font-semibold text-[var(--tessera-text)]">
            {t("detail.actions")}
          </p>
          <ul className="flex flex-col gap-1">
            {[t("detail.viewSignal"), t("detail.viewEvals")].map((label) => (
              <li key={label}>
                <button
                  type="button"
                  className="flex w-full items-center gap-1.5 text-left text-[0.66rem] text-[#87bfff] hover:text-[#a9d2ff]"
                >
                  <FileSearch className="h-3 w-3 shrink-0" /> {label}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-1 text-[0.62rem] font-semibold text-[var(--tessera-text)]">
            {t("detail.usage")}
          </p>
          <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
            {t("detail.loggedBy", { n: s.usage.logged_by })}
          </p>
          <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
            {t("detail.monitors", { n: s.usage.monitors })}
          </p>
        </div>
      </div>
    </aside>
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

// ── atoms ────────────────────────────────────────────────────────────────────

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

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0 truncate text-right text-[var(--tessera-text)]">{value}</dd>
    </div>
  );
}

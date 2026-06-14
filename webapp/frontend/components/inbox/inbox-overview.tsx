"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronRight, Layers, RefreshCcw, Search } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { fetchInboxOverview } from "@/lib/api/client";
import type { InboxOverview as InboxData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const PRIORITY: Record<string, string> = {
  urgent: "border-red-500/30 bg-red-500/15 text-red-300",
  high: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  medium: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  low: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
};
const STATUS: Record<string, string> = {
  todo: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  in_progress: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  waiting: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  resolved: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const SLA_TONE: Record<string, string> = {
  crit: "text-red-300",
  warn: "text-amber-300",
  ok: "text-emerald-300",
};

type T = ReturnType<typeof useTranslations<"inbox">>;
type Data = InboxData;

export function InboxOverview() {
  const t = useTranslations("inbox");
  const { data } = useQuery({
    queryKey: ["inbox-overview"],
    queryFn: ({ signal }) => fetchInboxOverview(signal),
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

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <Rail t={t} data={data} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        {data.kpis.map((kpi) => (
          <CompactKpi key={kpi.key} kpi={kpi} label={t(`kpi.${kpi.key}`)} vs={t("delta.vsHier")} />
        ))}
      </div>

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
        <TaskTable t={t} data={data} />
        <aside className="flex min-w-0 flex-col gap-3">
          <ByType t={t} data={data} />
          <Sla t={t} data={data} />
          <Activity t={t} data={data} />
        </aside>
      </div>

      <Footer t={t} data={data} />
    </div>
  );
}

// ── rail ─────────────────────────────────────────────────────────────────────

function Rail({ t, data }: { t: T; data: Data }) {
  const r = data.rail;
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-2 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <span className="flex items-center gap-1.5 font-medium text-[var(--tessera-green)]">
        <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--tessera-green)]" />{" "}
        {t("rail.live")}
      </span>
      <span className="text-[var(--tessera-text-muted)]">{t("rail.queue")}</span>
      <Sep />
      <span className="text-[var(--tessera-text-muted)]">{t("rail.realtime")}</span>
      <Sep />
      <span className="text-[var(--tessera-text-muted)]">
        {t("rail.period")} : <span className="text-[var(--tessera-text)]">{r.period}</span>
      </span>
      <Sep />
      <span className="text-[var(--tessera-text-muted)]">
        {t("rail.updated")} :{" "}
        <span className="tabular-nums text-[var(--tessera-text)]">{r.updated}</span>
      </span>
      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          className="flex h-8 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)]"
        >
          <RefreshCcw className="h-3.5 w-3.5" /> {t("rail.replay")}
        </button>
        <Button
          size="sm"
          className="h-8 gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/60 px-3 text-xs text-[#c4b5fd] hover:bg-[#4c3fb0]/80"
        >
          <Layers className="h-3.5 w-3.5" /> {t("rail.bulk")}
        </Button>
      </div>
    </section>
  );
}

function CompactKpi({ kpi, label, vs }: { kpi: Data["kpis"][number]; label: string; vs: string }) {
  const up = kpi.delta_label.trim().startsWith("+");
  const good = up === kpi.good_is_up;
  return (
    <div className="flex h-[96px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="truncate text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
        {label}
      </p>
      <p className="mt-0.5 whitespace-nowrap text-[1.35rem] font-semibold leading-none text-white">
        {kpi.value}
      </p>
      <p
        className={cn(
          "mt-0.5 text-[0.58rem] font-medium",
          good ? "text-[var(--tessera-green)]" : "text-red-300",
        )}
      >
        {kpi.delta_label} {vs}
      </p>
      <MetricSparkline
        className="mt-auto h-4 w-full"
        values={kpi.series}
        tone={kpi.good_is_up ? "success" : "danger"}
      />
    </div>
  );
}

// ── table ────────────────────────────────────────────────────────────────────

function TaskTable({ t, data }: { t: T; data: Data }) {
  const cols = ["priority", "type", "title", "source", "assignee", "sla", "due", "status"] as const;
  return (
    <div className="flex min-w-0 flex-col gap-3">
      <section className="flex min-h-[48px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
          <input
            type="search"
            placeholder={t("filters.search")}
            className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none"
          />
        </div>
        {(["priority", "type", "status", "assignee"] as const).map((f) => (
          <div
            key={f}
            className="flex h-9 shrink-0 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)]"
          >
            {t(`filters.${f}`)} <ChevronRight className="h-3.5 w-3.5 rotate-90" />
          </div>
        ))}
      </section>

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
              {data.items.map((it) => (
                <tr
                  key={it.id}
                  className="cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors last:border-0 hover:bg-[#0b2b49]"
                >
                  <td className="px-2 py-1.5">
                    <Badge className={PRIORITY[it.priority]}>{t(`priority.${it.priority}`)}</Badge>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {t(`type.${it.type}`)}
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="text-[var(--tessera-text)]">{it.title}</span>
                    <span className="ml-1.5 font-mono text-[0.56rem] text-[var(--tessera-text-muted)]">
                      {it.id}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{it.source}</td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{it.assignee}</td>
                  <td
                    className={cn(
                      "whitespace-nowrap px-2 py-1.5 font-medium tabular-nums",
                      SLA_TONE[it.sla_tone],
                    )}
                  >
                    {it.sla}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                    {it.due}
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={STATUS[it.status]}>{t(`status.${it.status}`)}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
          <span>
            1–{data.items.length} / {data.total_items}
          </span>
        </div>
      </div>
    </div>
  );
}

// ── right column ─────────────────────────────────────────────────────────────

function ByType({ t, data }: { t: T; data: Data }) {
  const sum = data.by_type.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <Panel title={t("zone.byType")} action={<ViewAll label={t("sla.viewDetail")} />}>
      <div className="flex items-center gap-3">
        <div className="relative h-[88px] w-[88px] shrink-0">
          <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
            <circle
              cx="36"
              cy="36"
              r={R}
              fill="none"
              stroke="var(--tessera-border)"
              strokeWidth="9"
            />
            {data.by_type.map((s) => {
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
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-base font-semibold tabular-nums text-white">
              {data.by_type_total}
            </span>
            <span className="text-[0.46rem] uppercase text-[var(--tessera-text-muted)]">Total</span>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
          {data.by_type.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                {t(`type.${s.key}`)}
              </span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {s.count} ({s.pct}%)
              </span>
            </li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function Sla({ t, data }: { t: T; data: Data }) {
  const max = Math.max(...data.sla_buckets.map((b) => b.count), 1);
  return (
    <Panel title={t("zone.sla")} action={<ViewAll label={t("sla.viewSla")} />}>
      <ul className="flex flex-col gap-2">
        {data.sla_buckets.map((b) => (
          <li key={b.key} className="flex items-center gap-2 text-[0.68rem]">
            <span className="w-16 shrink-0 text-[var(--tessera-text)]">{t(`sla.${b.key}`)}</span>
            <div className="h-1.5 flex-1 rounded-full bg-[var(--tessera-bg)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${(b.count / max) * 100}%`, background: b.color }}
              />
            </div>
            <span className="w-5 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
              {b.count}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Activity({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title={t("zone.activity")}>
      <ul className="flex flex-col gap-1.5">
        {data.recent_activity.map((a) => (
          <li key={`${a.time}-${a.action}`} className="flex items-center gap-2 text-[0.66rem]">
            <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-400" />
            <span className="font-medium text-[var(--tessera-text)]">{a.actor}</span>
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
              {a.action}
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">{a.time}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Panel({
  title,
  action,
  children,
}: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
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

function Sep() {
  return <span className="hidden text-[var(--tessera-border-strong)] sm:inline">·</span>;
}

function ViewAll({ label }: { label: string }) {
  return (
    <button
      type="button"
      className="flex shrink-0 items-center gap-0.5 text-[0.64rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]"
    >
      {label} <ChevronRight className="h-3 w-3" />
    </button>
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

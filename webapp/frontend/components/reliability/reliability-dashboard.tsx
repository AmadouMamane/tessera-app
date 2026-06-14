"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Activity, Boxes, Coins, type LucideIcon, ShieldCheck, Timer, Wrench } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { type Period, PeriodRail } from "@/components/observability/period-rail";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchReliability } from "@/lib/api/client";
import type {
  ReliabilityActionRow,
  ReliabilityCostRow,
  ReliabilityIncident,
  ReliabilityServiceRow,
} from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";

const ERR_COLOR: Record<string, string> = {
  token_spike: "#f59e0b",
  tool_denied: "#60a5fa",
  tool_error: "#ef4444",
  arg_failure: "#a78bfa",
  low_quality: "#f472b6",
};

const TABS = [
  "overview",
  "reliability",
  "cost",
  "performance",
  "quotas",
  "incidents",
  "capacity",
] as const;

const eur = (v: number, d = 2) =>
  `€${v.toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d })}`;
const ms = (v: number | null) =>
  v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`;
const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);

function Sec({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
      {children}
    </h2>
  );
}

/** A translucent banded section grouping one cockpit zone (A · B · C · …). */
function Zone({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--tessera-border)]/50 bg-[var(--tessera-surface)]/25 p-2.5">
      <Sec>{label}</Sec>
      <div className="mt-1.5">{children}</div>
    </section>
  );
}

/** Tiny sparkline over a real value series. A flat series reads as a steady mid line. */
function Spark({ values }: { values: number[] }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const flat = max - min === 0;
  const span = max - min || 1;
  const W = 100;
  const H = 22;
  const d = values
    .map(
      (v, i) =>
        `${i === 0 ? "M" : "L"}${((i / (values.length - 1)) * W).toFixed(1)},${(
          flat ? H / 2 : H - ((v - min) / span) * H
        ).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-5 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={d} fill="none" stroke="#10b981" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

function Panel({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <Card className="flex h-full min-w-0 flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-[0.78rem] font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1">
        {children}
        {note ? <p className="mt-1 text-[0.6rem] text-[var(--muted-foreground)]">{note}</p> : null}
      </CardContent>
    </Card>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  sub,
  tone,
  series,
  delta,
  deltaUnit,
  deltaUpIsGood,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  tone?: string;
  series?: number[];
  delta?: number | null;
  deltaUnit?: "pts" | "%";
  deltaUpIsGood?: boolean;
}) {
  const tr = useTranslations("reliability");
  const showDelta = delta != null && Math.abs(delta) >= 0.005;
  const up = (delta ?? 0) > 0;
  const deltaGood = up === (deltaUpIsGood ?? true);
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <div className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
      </div>
      {showDelta ? (
        <div className="flex items-center gap-1 text-[0.65rem] tabular-nums">
          <span className={`whitespace-nowrap ${deltaGood ? GOOD : BAD}`}>
            {up ? "↗" : "↘"} {Math.abs((delta as number) * 100).toFixed(0)}
            {deltaUnit === "%" ? " %" : ` ${tr("kpi.pts")}`}
          </span>
          <span className="truncate text-[var(--muted-foreground)]">{tr("kpi.vsPrev")}</span>
        </div>
      ) : sub ? (
        <div className="truncate text-[0.65rem] text-[var(--muted-foreground)]">{sub}</div>
      ) : null}
      {series && series.length > 1 ? <Spark values={series} /> : null}
    </Card>
  );
}

/** Donut from labelled slices. */
function Donut({ slices }: { slices: { label: string; count: number; color: string }[] }) {
  const total = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[80px] w-[80px] shrink-0">
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
            const frac = s.count / total;
            const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
            off += frac;
            return (
              <circle
                key={s.label}
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
        <div className="absolute inset-0 flex items-center justify-center text-base font-semibold tabular-nums">
          {total}
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.7rem]">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate">{s.label}</span>
            <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
              {s.count} · {Math.round((s.count / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function LatStat({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-[0.72rem] text-[var(--muted-foreground)]">{label}</span>
      <span className={`text-lg font-semibold tabular-nums ${tone}`}>{value}</span>
    </div>
  );
}

/** Multi-line chart over a shared X (one point per day), with a small legend. */
function MultiLine({
  lines,
  format,
}: {
  lines: { label: string; color: string; values: (number | null)[] }[];
  format: (v: number) => string;
}) {
  const all = lines.flatMap((l) => l.values.filter((v): v is number => v != null));
  if (all.length < 2)
    return <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>;
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const W = 240;
  const H = 70;
  const n = Math.max(...lines.map((l) => l.values.length));
  const path = (vals: (number | null)[]) => {
    const pts = vals
      .map((v, i) =>
        v == null
          ? null
          : `${((i / Math.max(1, n - 1)) * W).toFixed(1)},${(H - 4 - ((v - min) / span) * (H - 8)).toFixed(1)}`,
      )
      .filter((p): p is string => p != null);
    return pts.length < 2 ? "" : `M${pts.join(" L")}`;
  };
  return (
    <div className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-20 w-full"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {lines.map((l) => (
          <path
            key={l.label}
            d={path(l.values)}
            fill="none"
            stroke={l.color}
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        ))}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.6rem] text-[var(--muted-foreground)]">
        {lines.map((l) => {
          const last = [...l.values].reverse().find((v): v is number => v != null);
          return (
            <span key={l.label} className="flex items-center gap-1">
              <span className="h-1 w-3 rounded-full" style={{ background: l.color }} />
              {l.label}
              {last != null ? (
                <b className="font-semibold text-[var(--foreground)]">{format(last)}</b>
              ) : null}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** Vertical bar chart, one bar per day. */
function DayBars({
  values,
  color = "#34d399",
  format,
}: {
  values: number[];
  color?: string;
  format: (v: number) => string;
}) {
  if (values.length === 0)
    return <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>;
  const max = Math.max(0.000001, ...values);
  const total = values.reduce((s, v) => s + v, 0);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-20 items-end gap-0.5">
        {values.map((v, i) => (
          <div
            // biome-ignore lint/suspicious/noArrayIndexKey: daily bars are positional
            key={i}
            className="flex-1 rounded-t-sm"
            style={{ height: `${Math.max(3, (v / max) * 100)}%`, background: color }}
            title={format(v)}
          />
        ))}
      </div>
      <div className="text-[0.6rem] text-[var(--muted-foreground)]">{format(total)}</div>
    </div>
  );
}

const POLL = 30_000;

export function ReliabilityDashboard() {
  const tr = useTranslations("reliability");
  const [period, setPeriod] = useState<Period>({ days: 30, anchor: null });
  const q = useQuery({
    queryKey: ["reliability", period.days, period.anchor],
    queryFn: ({ signal }) => fetchReliability(signal, period.days, period.anchor),
    placeholderData: keepPreviousData,
    refetchInterval: period.anchor ? false : POLL,
  });
  const d = q.data;

  if (!d?.available) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-[var(--muted-foreground)]">
          {q.isLoading ? tr("loading") : tr("unavailable")}
        </CardContent>
      </Card>
    );
  }

  const errSlices = (d.error_breakdown ?? []).map((s) => ({
    label: tr(`err.${s.label}`),
    count: s.count,
    color: ERR_COLOR[s.label] ?? "#94a3b8",
  }));
  const budgetUsed = d.budget_monthly_eur ? (d.budget_spent_eur ?? 0) / d.budget_monthly_eur : 0;
  const daily = d.daily ?? [];
  const availLine = daily.map((p) => p.availability);
  const errLine = daily.map((p) => p.error_rate);
  const costDay = daily.map((p) => p.cost_eur);
  const provTotal = (d.providers ?? []).reduce((s, p) => s + p.n_requests, 0) || 1;

  return (
    <div className="flex flex-col gap-2">
      <nav className="flex min-w-0 items-center gap-1 overflow-x-auto border-b border-[var(--tessera-border)]">
        {TABS.map((t, i) => (
          <span
            key={t}
            className={`-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[0.8rem] ${i === 0 ? "border-[var(--tessera-green)] font-medium text-[var(--tessera-text)]" : "border-transparent text-[var(--muted-foreground)]"}`}
          >
            {tr(`tabs.${t}`)}
          </span>
        ))}
      </nav>

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="flex min-w-0 flex-col gap-2">
          {/* A. Posture opérationnelle */}
          <Zone label={tr("sec.actual")}>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
              <Kpi
                icon={ShieldCheck}
                label={tr("kpi.availability")}
                value={pct(d.availability, 2)}
                tone={(d.availability ?? 0) >= 0.99 ? GOOD : WARN}
                sub={tr("kpi.sla")}
                series={availLine}
              />
              <Kpi
                icon={Activity}
                label={tr("kpi.errorRate")}
                value={pct(d.error_rate, 2)}
                tone={(d.error_rate ?? 0) < 0.01 ? GOOD : WARN}
                series={errLine}
              />
              <Kpi
                icon={Timer}
                label={tr("kpi.p50")}
                value={ms(d.latency_p50_ms ?? null)}
                tone={GOOD}
                sub={tr("kpi.estimated")}
              />
              <Kpi
                icon={Timer}
                label={tr("kpi.p95")}
                value={ms(d.latency_p95_ms ?? null)}
                tone={WARN}
                sub={tr("kpi.estimated")}
              />
              <Kpi
                icon={Wrench}
                label={tr("kpi.toolSuccess")}
                value={pct(d.tool_success, 2)}
                tone={(d.tool_success ?? 0) >= 0.95 ? GOOD : WARN}
              />
              <Kpi
                icon={Coins}
                label={tr("kpi.totalCost")}
                value={eur(d.total_cost_eur ?? 0, 4)}
                tone={GOOD}
                sub={tr("kpi.window")}
                series={costDay}
                delta={d.volume_delta}
                deltaUnit="%"
                deltaUpIsGood={false}
              />
              <Kpi
                icon={Coins}
                label={tr("kpi.costPerReq")}
                value={eur(d.cost_per_request_eur ?? 0, 6)}
                tone={GOOD}
              />
              <Kpi
                icon={Boxes}
                label={tr("kpi.requests")}
                value={`${(d.n_requests ?? 0).toLocaleString("fr-FR")}`}
                sub={`${(d.total_tokens ?? 0).toLocaleString("fr-FR")} ${tr("kpi.tokens")}`}
                series={d.volume_series}
                delta={d.volume_delta}
                deltaUnit="%"
                deltaUpIsGood
              />
            </div>
          </Zone>

          {/* B. Fiabilité & budget */}
          <Zone label={tr("sec.reliability")}>
            <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
              <Panel title={tr("panel.availErrors")} note={tr("panel.availNote")}>
                <MultiLine
                  lines={[
                    { label: tr("leg.availability"), color: "#34d399", values: availLine },
                    { label: tr("leg.error"), color: "#ef4444", values: errLine },
                  ]}
                  format={(v) => pct(v, 0)}
                />
              </Panel>
              <Panel title={tr("panel.errors", { n: errSlices.reduce((s, x) => s + x.count, 0) })}>
                {errSlices.length === 0 ? (
                  <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                    {tr("noErrors")}
                  </p>
                ) : (
                  <Donut slices={errSlices} />
                )}
              </Panel>
              <Panel title={tr("panel.latency")} note={tr("panel.latencyNote")}>
                <div className="flex flex-col gap-2">
                  <LatStat label={tr("leg.p50")} value={ms(d.latency_p50_ms ?? null)} tone={GOOD} />
                  <LatStat label={tr("leg.p95")} value={ms(d.latency_p95_ms ?? null)} tone={WARN} />
                  <LatStat label={tr("leg.p99")} value={ms(d.latency_p99_ms ?? null)} tone={BAD} />
                </div>
              </Panel>
              <Panel title={tr("panel.costPerDay")}>
                <DayBars values={costDay} format={(v) => eur(v, 4)} />
              </Panel>
            </div>
          </Zone>

          {/* C. Coûts & services */}
          <Zone label={tr("sec.cost")}>
            <div className="grid gap-2 lg:grid-cols-2">
              <Panel title={tr("panel.costByModel", { n: d.models?.length ?? 0 })}>
                <div className="overflow-x-auto">
                  <table className="w-full text-[0.72rem]">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                        <th className="py-1 pr-2 font-medium">{tr("col.model")}</th>
                        <th className="py-1 pr-2 font-medium">{tr("col.provider")}</th>
                        <th className="py-1 pr-2 text-right font-medium">{tr("col.requests")}</th>
                        <th className="py-1 pr-2 text-right font-medium">{tr("col.cost")}</th>
                        <th className="py-1 pr-2 text-right font-medium">{tr("col.passRate")}</th>
                        <th className="py-1 text-right font-medium">{tr("col.latency")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(d.models ?? []).map((m) => (
                        <ModelRow key={m.model} m={m} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
              <Panel title={tr("panel.topServices", { n: d.services_cost?.length ?? 0 })}>
                <table className="w-full text-[0.72rem]">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                      <th className="py-1 pr-2 font-medium">{tr("col.service")}</th>
                      <th className="py-1 pr-2 text-right font-medium">{tr("col.requests")}</th>
                      <th className="py-1 pr-2 text-right font-medium">{tr("col.cost")}</th>
                      <th className="py-1 text-right font-medium">{tr("col.share")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.services_cost ?? []).map((s) => (
                      <tr key={s.name} className="border-b border-[var(--border)]/50">
                        <td className="py-1 pr-2">{s.name}</td>
                        <td className="py-1 pr-2 text-right tabular-nums">{s.n_requests}</td>
                        <td className="py-1 pr-2 text-right tabular-nums">{eur(s.cost_eur, 4)}</td>
                        <td className="py-1 text-right tabular-nums text-[var(--muted-foreground)]">
                          {pct(s.share, 0)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
              <Panel title={tr("panel.incidents", { n: d.incidents?.length ?? 0 })}>
                {(d.incidents ?? []).length === 0 ? (
                  <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                    {tr("noIncidents")}
                  </p>
                ) : (
                  <table className="w-full text-[0.7rem]">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                        <th className="py-1 pr-2 font-medium">{tr("col.date")}</th>
                        <th className="py-1 pr-2 font-medium">{tr("col.type")}</th>
                        <th className="py-1 pr-2 font-medium">{tr("col.service")}</th>
                        <th className="py-1 text-right font-medium">{tr("col.severity")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(d.incidents ?? []).map((inc, i) => (
                        <IncidentRow key={`${inc.type}-${i}`} inc={inc} />
                      ))}
                    </tbody>
                  </table>
                )}
              </Panel>
              <Panel title={tr("panel.actions", { n: d.actions?.length ?? 0 })}>
                <table className="w-full text-[0.7rem]">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                      <th className="py-1 pr-2 font-medium">{tr("col.priority")}</th>
                      <th className="py-1 pr-2 font-medium">{tr("col.action")}</th>
                      <th className="py-1 pr-2 font-medium">{tr("col.impact")}</th>
                      <th className="py-1 text-right font-medium">{tr("col.complexity")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.actions ?? []).map((a) => (
                      <ActionRow key={a.priority} a={a} />
                    ))}
                  </tbody>
                </table>
              </Panel>
            </div>
          </Zone>

          {/* D. Performance & budget */}
          <Zone label={tr("sec.performance")}>
            <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
              <Panel title={tr("panel.services")}>
                <table className="w-full text-[0.72rem]">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                      <th className="py-1 pr-2 font-medium">{tr("col.service")}</th>
                      <th className="py-1 pr-2 text-right font-medium">{tr("col.success")}</th>
                      <th className="py-1 pr-2 text-right font-medium">{tr("col.p50")}</th>
                      <th className="py-1 text-right font-medium">{tr("col.requests")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.services ?? []).map((s) => (
                      <ServiceRow key={s.name} s={s} />
                    ))}
                  </tbody>
                </table>
              </Panel>
              <Panel title={tr("panel.providerBreakdown", { n: (d.providers ?? []).length })}>
                <div className="flex flex-col gap-1.5">
                  {(d.providers ?? []).map((p) => (
                    <div key={p.provider} className="flex items-center gap-2 text-[0.72rem]">
                      <span className="w-20 shrink-0 truncate">{p.provider}</span>
                      <div className="h-2 flex-1 overflow-hidden rounded-sm bg-[var(--tessera-muted)]/50">
                        <div
                          className="h-full rounded-sm bg-[#60a5fa]"
                          style={{ width: `${(p.n_requests / provTotal) * 100}%` }}
                        />
                      </div>
                      <span className="w-20 shrink-0 text-right tabular-nums text-[var(--muted-foreground)]">
                        {Math.round((p.n_requests / provTotal) * 100)}% · {p.n_requests}
                      </span>
                    </div>
                  ))}
                </div>
              </Panel>
              <Panel title={tr("panel.budgetForecast")}>
                <div className="flex flex-col gap-1.5 text-[0.72rem]">
                  <div className="mb-1 flex items-end gap-2">
                    <span className="text-2xl font-semibold tabular-nums">
                      {eur(d.budget_spent_eur ?? 0)}
                    </span>
                    <span className="pb-1 text-xs text-[var(--muted-foreground)]">
                      / {eur(d.budget_monthly_eur ?? 0, 0)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--tessera-muted)]/50">
                    <div
                      className="h-full rounded-full bg-[var(--tessera-green)]"
                      style={{ width: `${Math.min(100, budgetUsed * 100)}%` }}
                    />
                  </div>
                  <Row label={tr("bf.monthly")} value={eur(d.budget_monthly_eur ?? 0, 0)} />
                  <Row
                    label={tr("bf.spent")}
                    value={`${eur(d.budget_spent_eur ?? 0)} · ${pct(budgetUsed, 0)}`}
                  />
                  <Row label={tr("bf.projected")} value={eur(d.budget_projected_eur ?? 0)} />
                  <Badge tone={d.within_budget ? "success" : "danger"}>
                    {d.within_budget ? tr("bf.within") : tr("bf.over")}
                  </Badge>
                </div>
              </Panel>
              <Panel title={tr("rail.qualityTrend")} note={tr("rail.qualityTrendNote")}>
                {(d.quality_series ?? []).length > 1 ? (
                  <div className="flex flex-col gap-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-xl font-semibold tabular-nums">
                        {Math.round(((d.quality_series ?? []).at(-1) ?? 0) * 100)}%
                      </span>
                      {d.quality_delta != null && Math.abs(d.quality_delta) >= 0.005 ? (
                        <span
                          className={`text-[0.7rem] tabular-nums ${d.quality_delta > 0 ? GOOD : BAD}`}
                        >
                          {d.quality_delta > 0 ? "↗" : "↘"}{" "}
                          {Math.abs(d.quality_delta * 100).toFixed(0)} {tr("kpi.pts")}
                        </span>
                      ) : null}
                    </div>
                    <Spark values={d.quality_series ?? []} />
                  </div>
                ) : (
                  <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>
                )}
              </Panel>
            </div>
          </Zone>
        </div>

        <PeriodRail
          title={tr("period.title")}
          items={(d.daily ?? [])
            .filter((p) => p.date)
            .map((p) => ({ stamp: p.date, label: fmtDate(p.date) }))
            .reverse()}
          presets={[
            { value: 7, label: tr("period.d7") },
            { value: 14, label: tr("period.d14") },
            { value: 30, label: tr("period.d30") },
          ]}
          value={period}
          onApply={setPeriod}
          labels={{
            selected: tr("period.selected"),
            from: tr("period.from"),
            apply: tr("period.apply"),
            noData: tr("noIncidents"),
          }}
        />
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--muted-foreground)]">
        <Chip icon={ShieldCheck} label={tr("status.chain")} tone="text-[var(--tessera-green)]" />
        <Chip icon={Boxes} label={tr("status.truth")} />
        <Chip icon={Activity} label={tr("status.soc")} />
      </div>
    </div>
  );
}

function ModelRow({ m }: { m: ReliabilityCostRow }) {
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2 font-mono text-[0.68rem]">{m.model}</td>
      <td className="py-1 pr-2 text-[var(--muted-foreground)]">{m.provider}</td>
      <td className="py-1 pr-2 text-right tabular-nums">{m.n_requests}</td>
      <td className="py-1 pr-2 text-right tabular-nums">{eur(m.cost_eur, 4)}</td>
      <td
        className={`py-1 pr-2 text-right tabular-nums ${m.pass_rate != null && m.pass_rate >= 0.8 ? GOOD : WARN}`}
      >
        {m.pass_rate == null ? "—" : `${Math.round(m.pass_rate * 100)}%`}
      </td>
      <td className="py-1 text-right tabular-nums text-[var(--muted-foreground)]">
        {ms(m.latency_ms)}
      </td>
    </tr>
  );
}

function ServiceRow({ s }: { s: ReliabilityServiceRow }) {
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2">{s.name}</td>
      <td
        className={`py-1 pr-2 text-right tabular-nums ${s.success >= 0.9 ? GOOD : s.success >= 0.6 ? WARN : BAD}`}
      >
        {Math.round(s.success * 100)}%
      </td>
      <td className="py-1 pr-2 text-right tabular-nums text-[var(--muted-foreground)]">
        {ms(s.latency_p50_ms)}
      </td>
      <td className="py-1 text-right tabular-nums">{s.n_requests}</td>
    </tr>
  );
}

const SEV_BADGE: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};
const fmtDate = (iso: string) => {
  const parts = iso.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : iso;
};

function IncidentRow({ inc }: { inc: ReliabilityIncident }) {
  const tr = useTranslations("reliability");
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2 tabular-nums text-[var(--muted-foreground)]">
        {inc.date ? fmtDate(inc.date) : "—"}
      </td>
      <td className="py-1 pr-2">
        <span className="truncate">{tr(`err.${inc.type}`)}</span>
      </td>
      <td className="py-1 pr-2 text-[var(--muted-foreground)]">{inc.service || "—"}</td>
      <td className="py-1 text-right">
        <Badge tone={SEV_BADGE[inc.severity] ?? "neutral"}>{inc.detail}</Badge>
      </td>
    </tr>
  );
}

function ActionRow({ a }: { a: ReliabilityActionRow }) {
  const good = a.impact.startsWith("+");
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2 tabular-nums text-[var(--tessera-green)]">{a.priority}</td>
      <td className="py-1 pr-2">{a.action}</td>
      <td className={`py-1 pr-2 tabular-nums ${good ? GOOD : WARN}`}>{a.impact}</td>
      <td className="py-1 text-right text-[var(--muted-foreground)]">{a.complexity}</td>
    </tr>
  );
}

function Chip({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
      <Icon className={`h-3.5 w-3.5 shrink-0 ${tone ?? ""}`} />
      <span className="truncate">{label}</span>
    </span>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  CalendarClock,
  Coins,
  type LucideIcon,
  ShieldCheck,
  Timer,
  Wrench,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchReliability } from "@/lib/api/client";
import type {
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

function Panel({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-[0.78rem] font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
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
}: { icon: LucideIcon; label: string; value: string; sub?: string; tone?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <div className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
      </div>
      {sub ? (
        <div className="truncate text-[0.65rem] text-[var(--muted-foreground)]">{sub}</div>
      ) : null}
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

function Bar({
  label,
  value,
  max,
  tone,
}: { label: string; value: number; max: number; tone?: string }) {
  return (
    <div className="flex items-center gap-2 text-[0.72rem]">
      <span className="w-20 shrink-0 truncate">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-sm bg-[var(--tessera-muted)]/50">
        <div
          className="h-full rounded-sm"
          style={{ width: `${(value / (max || 1)) * 100}%`, background: tone ?? "#60a5fa" }}
        />
      </div>
      <span className="w-12 shrink-0 text-right tabular-nums text-[var(--muted-foreground)]">
        {value}
      </span>
    </div>
  );
}

const POLL = 30_000;

export function ReliabilityDashboard() {
  const tr = useTranslations("reliability");
  const q = useQuery({
    queryKey: ["reliability"],
    queryFn: ({ signal }) => fetchReliability(signal),
    refetchInterval: POLL,
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
  const maxProv = Math.max(1, ...(d.providers ?? []).map((p) => p.n_requests));
  const budgetUsed = d.budget_monthly_eur ? (d.budget_spent_eur ?? 0) / d.budget_monthly_eur : 0;

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

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        <Kpi
          icon={ShieldCheck}
          label={tr("kpi.availability")}
          value={pct(d.availability, 2)}
          tone={(d.availability ?? 0) >= 0.99 ? GOOD : WARN}
          sub={tr("kpi.sla")}
        />
        <Kpi
          icon={Activity}
          label={tr("kpi.errorRate")}
          value={pct(d.error_rate, 2)}
          tone={(d.error_rate ?? 0) < 0.01 ? GOOD : WARN}
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
        />
      </div>

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-2">
          {/* Row 1 — errors donut · providers · budget */}
          <div className="grid items-start gap-2 lg:grid-cols-3">
            <Panel title={tr("panel.errors", { n: errSlices.reduce((s, x) => s + x.count, 0) })}>
              {errSlices.length === 0 ? (
                <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">
                  {tr("noErrors")}
                </p>
              ) : (
                <Donut slices={errSlices} />
              )}
            </Panel>
            <Panel title={tr("panel.providers")}>
              <div className="flex flex-col gap-1.5">
                {(d.providers ?? []).map((p) => (
                  <Bar key={p.provider} label={p.provider} value={p.n_requests} max={maxProv} />
                ))}
              </div>
            </Panel>
            <Panel title={tr("panel.budget")} note={tr("panel.budgetNote")}>
              <div className="flex items-end gap-2">
                <span className="text-2xl font-semibold tabular-nums">
                  {eur(d.budget_spent_eur ?? 0)}
                </span>
                <span className="pb-1 text-xs text-[var(--muted-foreground)]">
                  / {eur(d.budget_monthly_eur ?? 0, 0)}
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--tessera-muted)]/50">
                <div
                  className="h-full rounded-full bg-[var(--tessera-green)]"
                  style={{ width: `${Math.min(100, budgetUsed * 100)}%` }}
                />
              </div>
              <div className="mt-1 flex justify-between text-[0.65rem] text-[var(--muted-foreground)]">
                <span>{pct(budgetUsed)}</span>
                <span>
                  {tr("panel.projected")}: {eur(d.budget_projected_eur ?? 0)}
                </span>
              </div>
            </Panel>
          </div>

          {/* Row 2 — cost by model */}
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

          {/* Row 3 — performance par service · incidents */}
          <div className="grid items-start gap-2 lg:grid-cols-2">
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
            <Panel title={tr("panel.incidents", { n: d.incidents?.length ?? 0 })}>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {(d.incidents ?? []).length === 0 ? (
                  <li className="text-[var(--muted-foreground)]">{tr("noIncidents")}</li>
                ) : (
                  (d.incidents ?? []).map((inc, i) => (
                    <IncidentRow key={`${inc.type}-${i}`} inc={inc} />
                  ))
                )}
              </ul>
            </Panel>
          </div>
        </div>

        <ReliabilityRail
          spent={d.budget_spent_eur ?? 0}
          monthly={d.budget_monthly_eur ?? 0}
          projected={d.budget_projected_eur ?? 0}
          requests={d.n_requests ?? 0}
          cacheOverhead={d.cache_overhead_pct ?? 0}
          withinBudget={d.within_budget ?? true}
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

function IncidentRow({ inc }: { inc: ReliabilityIncident }) {
  return (
    <li className="flex items-center gap-2">
      <span
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${inc.severity === "high" ? "bg-red-500" : inc.severity === "medium" ? "bg-amber-500" : "bg-[var(--muted-foreground)]"}`}
      />
      <span className="min-w-0 flex-1 truncate">{inc.label}</span>
      <span className="shrink-0 text-[0.62rem] text-[var(--muted-foreground)]">{inc.detail}</span>
    </li>
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

function ReliabilityRail({
  spent,
  monthly,
  projected,
  requests,
  cacheOverhead,
  withinBudget,
}: {
  spent: number;
  monthly: number;
  projected: number;
  requests: number;
  cacheOverhead: number;
  withinBudget: boolean;
}) {
  const tr = useTranslations("reliability");
  const used = monthly ? spent / monthly : 0;
  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tr("rail.requests")}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-end justify-between gap-2">
            <span className="font-serif text-2xl font-semibold tabular-nums">
              {requests.toLocaleString("fr-FR")}
            </span>
            <Badge tone="success">{tr("rail.live")}</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tr("rail.forecast")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 text-[0.72rem]">
            <Row label={tr("rail.monthly")} value={eur(monthly, 0)} />
            <Row label={tr("rail.spent")} value={`${eur(spent)} · ${Math.round(used * 100)}%`} />
            <Row label={tr("rail.projected")} value={eur(projected)} />
            <Badge tone={withinBudget ? "success" : "danger"}>
              {withinBudget ? tr("rail.withinBudget") : tr("rail.overBudget")}
            </Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tr("rail.cache")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 text-[0.72rem]">
            <Row label={tr("rail.overhead")} value={`${(cacheOverhead * 100).toFixed(3)}%`} />
            <Row
              label={tr("rail.budgetHeadroom")}
              value={withinBudget ? tr("rail.ok") : tr("rail.tight")}
            />
          </CardContent>
        </Card>

        <Button
          size="sm"
          className="h-8 w-full justify-center gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
        >
          <CalendarClock className="h-3.5 w-3.5" /> {tr("rail.forecastCta")}
        </Button>
      </div>
    </aside>
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

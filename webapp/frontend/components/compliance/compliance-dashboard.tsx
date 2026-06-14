"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  BookText,
  CalendarClock,
  FileCheck2,
  FileDown,
  ListChecks,
  type LucideIcon,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchCompliance } from "@/lib/api/client";
import type { ComplianceFramework, ComplianceObligation, NonConformity } from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";

const STATUS_BADGE: Record<string, "success" | "warning" | "danger"> = {
  conformant: "success",
  partial: "warning",
  non_conformant: "danger",
};
const SEV_BADGE: Record<string, "danger" | "warning" | "neutral"> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

const TABS = [
  "overview",
  "mapping",
  "obligations",
  "evaluations",
  "incidents",
  "retention",
  "evidence",
  "registry",
] as const;

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

function Panel({
  title,
  action,
  children,
  className,
}: { title: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <Card className={`flex h-full min-w-0 flex-col ${className ?? ""}`}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="text-[0.78rem] font-medium">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent className="flex-1">{children}</CardContent>
    </Card>
  );
}

/** Tiny sparkline over a real value series. */
function Spark({ values }: { values: number[] }) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 100;
  const H = 22;
  const d = values
    .map(
      (v, i) =>
        `${i === 0 ? "M" : "L"}${((i / (values.length - 1)) * W).toFixed(1)},${(
          H - ((v - min) / span) * H
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

function Kpi({
  label,
  value,
  unit,
  sub,
  tone,
  series,
  delta,
  deltaUpIsGood,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  tone?: string;
  series?: number[];
  delta?: number | null;
  deltaUpIsGood?: boolean;
}) {
  const tc = useTranslations("compliance");
  const showDelta = delta != null && Math.abs(delta) >= 0.005;
  const up = (delta ?? 0) > 0;
  const deltaGood = up === (deltaUpIsGood ?? true);
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <div className="truncate text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
        {unit ? (
          <span className="text-base font-medium text-[var(--muted-foreground)]">{unit}</span>
        ) : null}
      </div>
      {showDelta ? (
        <div className="flex items-center gap-1 text-[0.65rem] tabular-nums">
          <span className={`whitespace-nowrap ${deltaGood ? GOOD : BAD}`}>
            {up ? "↗" : "↘"} {Math.abs((delta as number) * 100).toFixed(0)} {tc("kpi.pts")}
          </span>
          <span className="truncate text-[var(--muted-foreground)]">{tc("kpi.vsPrev")}</span>
        </div>
      ) : sub ? (
        <div className="truncate text-[0.65rem] text-[var(--muted-foreground)]">{sub}</div>
      ) : null}
      {series && series.length > 1 ? <Spark values={series} /> : null}
    </Card>
  );
}

/** Stacked conformance bar (conformant / partial / non-conformant). */
function StackBar({ c, p, n }: { c: number; p: number; n: number }) {
  const total = c + p + n || 1;
  return (
    <div className="flex h-2 w-24 overflow-hidden rounded-full">
      <div style={{ width: `${(c / total) * 100}%`, background: "#10b981" }} />
      <div style={{ width: `${(p / total) * 100}%`, background: "#f59e0b" }} />
      <div style={{ width: `${(n / total) * 100}%`, background: "#ef4444" }} />
    </div>
  );
}

/** Evidence-completeness donut. */
function EvidenceDonut({ completeness }: { completeness: number }) {
  const R = 30;
  const C = 2 * Math.PI * R;
  const tone = completeness >= 0.9 ? "#10b981" : completeness >= 0.7 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative h-[96px] w-[96px]">
      <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="40" cy="40" r={R} fill="none" stroke="var(--tessera-border)" strokeWidth="9" />
        <circle
          cx="40"
          cy="40"
          r={R}
          fill="none"
          stroke={tone}
          strokeWidth="9"
          strokeDasharray={`${completeness * C} ${C}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-semibold tabular-nums">
          {Math.round(completeness * 100)}%
        </span>
      </div>
    </div>
  );
}

const POLL = 30_000;

export function ComplianceDashboard() {
  const tc = useTranslations("compliance");
  const temporal = useTemporalState();
  const { historyMode } = temporal;
  const railTimeline = useRailTimeline();
  const q = useQuery({
    queryKey: ["compliance"],
    queryFn: ({ signal }) => fetchCompliance(signal),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const d = q.data;

  if (!d?.available) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-[var(--muted-foreground)]">
          {q.isLoading ? tc("loading") : tc("unavailable")}
        </CardContent>
      </Card>
    );
  }

  const fwLabel = (code: string) => d.frameworks?.find((f) => f.code === code)?.label ?? code;
  const evTotal = (d.evidence_valid ?? 0) + (d.evidence_missing ?? 0) + (d.evidence_blocking ?? 0);
  // Real posture trend from the durable quality-score log (sparkline + delta).
  const trend = d.score_series ?? [];

  return (
    <div className="flex flex-col gap-2">
      {/* tab bar */}
      <nav className="flex min-w-0 items-center gap-1 overflow-x-auto border-b border-[var(--tessera-border)]">
        {TABS.map((t, i) => (
          <span
            key={t}
            className={`-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[0.8rem] ${
              i === 0
                ? "border-[var(--tessera-green)] font-medium text-[var(--tessera-text)]"
                : "border-transparent text-[var(--muted-foreground)]"
            }`}
          >
            {tc(`tabs.${t}`)}
          </span>
        ))}
      </nav>

      {/* Shared temporal rail (Live / Replay as-of-T) */}
      <TemporalRail
        mode={temporal.mode}
        liveStatus={tc("status.realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        onModeChange={temporal.changeMode}
      />

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-2">
          {/* A. Posture réglementaire */}
          <Zone label={tc("sec.actual")}>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
              <Kpi
                label={tc("kpi.score")}
                value={`${d.score ?? 0}`}
                unit="/100"
                sub={tc("kpi.scoreSub")}
                tone={(d.score ?? 0) >= 80 ? GOOD : WARN}
                series={trend}
                delta={d.score_delta}
                deltaUpIsGood
              />
              <Kpi
                label={tc("kpi.obligations")}
                value={`${d.n_applied ?? 0}`}
                unit={`/${d.n_obligations ?? 0}`}
                sub={`${Math.round(((d.n_applied ?? 0) / (d.n_obligations || 1)) * 100)}%`}
                tone={GOOD}
                series={trend}
              />
              <Kpi
                label={tc("kpi.conformant")}
                value={`${d.n_conformant ?? 0}`}
                unit={`/${d.n_controls ?? 0}`}
                sub={`${Math.round(((d.n_conformant ?? 0) / (d.n_controls || 1)) * 100)}%`}
                tone={GOOD}
                series={trend}
              />
              <Kpi
                label={tc("kpi.partial")}
                value={`${d.n_partial ?? 0}`}
                sub={`${Math.round(((d.n_partial ?? 0) / (d.n_controls || 1)) * 100)}%`}
                tone={WARN}
              />
              <Kpi
                label={tc("kpi.nonConformant")}
                value={`${d.n_non_conformant ?? 0}`}
                sub={`${Math.round(((d.n_non_conformant ?? 0) / (d.n_controls || 1)) * 100)}%`}
                tone={(d.n_non_conformant ?? 0) > 0 ? BAD : GOOD}
              />
              <Kpi
                label={tc("kpi.residual")}
                value={`${d.n_residual_risk ?? 0}`}
                sub={tc("kpi.residualSub")}
                tone={WARN}
              />
              <Kpi
                label={tc("kpi.deadlines")}
                value={`${d.n_critical_deadlines ?? 0}`}
                sub={tc("kpi.deadlinesSub")}
                tone={(d.n_critical_deadlines ?? 0) > 0 ? BAD : GOOD}
              />
            </div>
          </Zone>

          {/* B. Cartographie · obligations · evidence */}
          <Zone label={tc("sec.mapping")}>
            <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1.3fr)_minmax(0,1fr)]">
              <Panel title={tc("panel.mapping")}>
                <table className="w-full text-[0.72rem]">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                      <th className="py-1 pr-2 font-medium">{tc("col.framework")}</th>
                      <th className="py-1 pr-2 font-medium">{tc("col.score")}</th>
                      <th className="py-1 font-medium">{tc("col.breakdown")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.frameworks ?? []).map((f) => (
                      <FrameworkRow key={f.code} f={f} />
                    ))}
                  </tbody>
                </table>
              </Panel>

              <Panel title={tc("panel.obligations", { n: d.obligations?.length ?? 0 })}>
                <table className="w-full text-[0.72rem]">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                      <th className="py-1 pr-2 font-medium">{tc("col.obligation")}</th>
                      <th className="py-1 pr-2 font-medium">{tc("col.status")}</th>
                      <th className="py-1 pr-2 font-medium">{tc("col.due")}</th>
                      <th className="py-1 font-medium">{tc("col.owner")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.obligations ?? []).slice(0, 6).map((o) => (
                      <ObligationRow key={o.name} o={o} fwLabel={fwLabel} />
                    ))}
                  </tbody>
                </table>
              </Panel>

              <Panel title={tc("panel.evidence")}>
                <div className="flex items-center gap-3">
                  <EvidenceDonut completeness={d.evidence_completeness ?? 0} />
                  <ul className="flex flex-col gap-1 text-[0.7rem]">
                    <EvRow
                      color="#10b981"
                      label={tc("evidence.valid")}
                      value={d.evidence_valid ?? 0}
                    />
                    <EvRow
                      color="#f59e0b"
                      label={tc("evidence.missing")}
                      value={d.evidence_missing ?? 0}
                    />
                    <EvRow
                      color="#ef4444"
                      label={tc("evidence.blocking")}
                      value={d.evidence_blocking ?? 0}
                    />
                    <li className="pt-1 text-[var(--muted-foreground)]">
                      {tc("evidence.total", { n: evTotal })}
                    </li>
                  </ul>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2 h-7 w-full justify-center text-[0.7rem]"
                >
                  {tc("evidence.export")}
                </Button>
              </Panel>
            </div>
          </Zone>

          {/* C. Contrôles · preuves manquantes · incidents */}
          <Zone label={tc("sec.controls")}>
            <div className="grid gap-2 lg:grid-cols-3">
              <Panel title={tc("panel.controls", { n: d.controls?.length ?? 0 })}>
                <ul className="flex flex-col gap-1 text-[0.72rem]">
                  {(d.controls ?? []).slice(0, 6).map((c) => (
                    <li key={c.id} className="flex items-center gap-2">
                      <span className="min-w-0 flex-1 truncate">{c.name}</span>
                      <Badge tone={STATUS_BADGE[c.status] ?? "neutral"}>
                        {tc(`status.${c.status}`)}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </Panel>

              <Panel title={tc("panel.missing")}>
                <ul className="flex flex-col gap-1 text-[0.72rem]">
                  {(d.controls ?? [])
                    .filter((c) => c.status !== "conformant")
                    .slice(0, 7)
                    .map((c) => (
                      <li key={c.id} className="flex items-center justify-between gap-2">
                        <span className="min-w-0 flex-1 truncate font-mono text-[0.65rem]">
                          {c.evidence_id}
                        </span>
                        <span className="shrink-0 text-[var(--muted-foreground)]">
                          {fwLabel(c.framework)}
                        </span>
                      </li>
                    ))}
                </ul>
              </Panel>

              <Panel title={tc("panel.incidents")}>
                <table className="w-full text-[0.7rem]">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                      <th className="py-1 pr-2 font-medium">{tc("col.nc")}</th>
                      <th className="py-1 pr-2 font-medium">{tc("col.severity")}</th>
                      <th className="py-1 font-medium">{tc("col.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(d.non_conformities ?? []).slice(0, 6).map((nc) => (
                      <tr key={nc.id} className="border-b border-[var(--border)]/50">
                        <td className="py-1 pr-2 font-mono text-[var(--tessera-green)]">{nc.id}</td>
                        <td className="py-1 pr-2">
                          <Badge tone={SEV_BADGE[nc.severity] ?? "neutral"}>
                            {tc(`sev.${nc.severity}`)}
                          </Badge>
                        </td>
                        <td className="py-1 text-[var(--muted-foreground)]">
                          {tc(`ncStatus.${nc.status}`)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            </div>
          </Zone>
        </div>

        <ComplianceRail
          obligations={d.obligations ?? []}
          nc={d.non_conformities ?? []}
          fwLabel={fwLabel}
        />
      </div>

      {/* footer */}
      <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--muted-foreground)]">
        <Chip icon={ShieldCheck} label={tc("status.chain")} tone="text-[var(--tessera-green)]" />
        <Chip icon={ScrollText} label={tc("status.truth")} />
        <Chip icon={FileCheck2} label={tc("status.env")} />
      </div>
    </div>
  );
}

function FrameworkRow({ f }: { f: ComplianceFramework }) {
  const tone = f.score >= 0.9 ? GOOD : f.score >= 0.7 ? WARN : BAD;
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2">{f.label}</td>
      <td className={`py-1 pr-2 tabular-nums ${tone}`}>{Math.round(f.score * 100)}%</td>
      <td className="py-1">
        <StackBar c={f.n_conformant} p={f.n_partial} n={f.n_non_conformant} />
      </td>
    </tr>
  );
}

function ObligationRow({
  o,
  fwLabel,
}: { o: ComplianceObligation; fwLabel: (c: string) => string }) {
  const tc = useTranslations("compliance");
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2">
        <span className="line-clamp-1 max-w-[12rem]">{o.name}</span>
        <span className="text-[0.6rem] text-[var(--muted-foreground)]">{fwLabel(o.framework)}</span>
      </td>
      <td className="py-1 pr-2">
        <Badge tone={STATUS_BADGE[o.status] ?? "neutral"}>{tc(`status.${o.status}`)}</Badge>
      </td>
      <td className="py-1 pr-2 tabular-nums text-[var(--muted-foreground)]">{o.due}</td>
      <td className="py-1 text-[var(--muted-foreground)]">{o.owner}</td>
    </tr>
  );
}

function EvRow({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <li className="flex items-center gap-1.5">
      <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{value}</span>
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

function ComplianceRail({
  obligations,
  nc,
  fwLabel,
}: {
  obligations: ComplianceObligation[];
  nc: NonConformity[];
  fwLabel: (c: string) => string;
}) {
  const tc = useTranslations("compliance");
  const criticalNc = nc.filter((n) => n.severity === "high");
  const actions = obligations.slice(0, 5);
  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tc("rail.lastEval")}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-2 text-[0.72rem]">
            <span className="font-serif text-base font-semibold tabular-nums">11/06/2026</span>
            <Badge tone="success">{tc("rail.live")}</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tc("rail.deadlines")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {obligations.slice(0, 4).map((o) => (
              <div key={o.name} className="flex items-center gap-2 text-[0.72rem]">
                <span className="min-w-0 flex-1 truncate">{o.name}</span>
                <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
                  {o.due}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tc("rail.criticalNc")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {criticalNc.length === 0 ? (
              <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tc("rail.noNc")}</p>
            ) : (
              criticalNc.slice(0, 4).map((n) => (
                <div key={n.id} className="flex items-center gap-2 text-[0.72rem]">
                  <span className="font-mono text-[var(--tessera-green)]">{n.id}</span>
                  <span className="min-w-0 flex-1 truncate text-[var(--muted-foreground)]">
                    {n.title}
                  </span>
                  <Badge tone={SEV_BADGE[n.severity] ?? "neutral"}>{tc(`sev.${n.severity}`)}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tc("rail.actions", { n: actions.length })}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {actions.map((o) => (
              <div
                key={o.name}
                className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-[0.72rem]"
              >
                <CalendarClock className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
                <span className="min-w-0 flex-1 truncate">{o.name}</span>
                <Badge tone={o.status === "non_conformant" ? "danger" : "warning"}>
                  {fwLabel(o.framework)}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tc("rail.quickActions")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-0.5">
            {[
              { key: "qaEvidence", icon: FileCheck2 },
              { key: "qaRemediation", icon: ListChecks },
              { key: "qaReport", icon: FileDown },
              { key: "qaRegistry", icon: BookText },
            ].map((a) => (
              <button
                key={a.key}
                type="button"
                className="flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.72rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
              >
                <a.icon className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{tc(`rail.${a.key}`)}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        <Button
          size="sm"
          className="h-8 w-full justify-center gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
        >
          {tc("rail.evidenceCta")}
        </Button>
      </div>
    </aside>
  );
}

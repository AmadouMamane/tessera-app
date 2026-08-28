"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  BookText,
  CalendarClock,
  FileCheck2,
  FileDown,
  GitBranch,
  LayoutDashboard,
  ListChecks,
  type LucideIcon,
  ScrollText,
  ShieldCheck,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { downloadBlob } from "@/components/agent/agent-subtab-shared";
import { CatalogTabView } from "@/components/cockpit/catalog-tab-view";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { ProvenanceNotice } from "@/components/cockpit/provenance-notice";
import { TabStrip } from "@/components/cockpit/tab-strip";
import { useRailTimeline, useTemporalState } from "@/components/overview/temporal-rail";
import { SignalCommandBar } from "@/components/surveiller/signal-command-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchCompliance } from "@/lib/api/client";
import type {
  BusinessLegalSignal,
  ComplianceFramework,
  ComplianceObligation,
  NonConformity,
} from "@/lib/api/schemas";
import { useDecimalFormat } from "@/lib/format-number";
import { useWindowStore } from "@/lib/stores/window-store";
import { showNumber, toneFor } from "@/lib/unread-is-not-zero";
import { useUrlBackedView } from "@/lib/use-url-backed-view";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";

/**
 * A reading that never arrived wears neither colour.
 *
 * A verdict needs a reading. The shape that stood here coalesced an absent one to zero and
 * compared it to a threshold, so a query that never answered came out on the reassuring side
 * of the comparison — GREEN for "no non-conformities", "no frozen releases", "no errors".
 * ADR 0026 — a witness that cannot see may never report "ok". `lib/unread-is-not-zero.ts`
 * carries the whole account, including why the file-level ratchet could not catch these.
 */
const UNREAD = "text-[var(--muted-foreground)]";
const TONE_BAD = { bad: BAD, good: GOOD, unread: UNREAD };
const TONE_WARN = { bad: WARN, good: GOOD, unread: UNREAD };

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
const BUSINESS_STATUS_BADGE: Record<string, "success" | "warning" | "neutral"> = {
  scored: "success",
  unknown: "warning",
  not_applicable: "neutral",
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
type TabKey = (typeof TABS)[number];

const TAB_ICONS: Record<TabKey, LucideIcon> = {
  overview: LayoutDashboard,
  mapping: GitBranch,
  obligations: BookText,
  evaluations: ListChecks,
  incidents: AlertTriangle,
  retention: CalendarClock,
  evidence: FileCheck2,
  registry: ScrollText,
};

function Sec({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-1 text-xs font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
      {children}
    </h2>
  );
}

/** A translucent banded section grouping one cockpit zone (A · B · C · …). */
function Zone({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section
      data-slot="card"
      className="rounded-xl border border-[var(--tessera-border)]/50 bg-[var(--tessera-surface)]/25 p-2.5"
    >
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
  infoKey,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  infoKey?: string;
}) {
  const te = useTranslations("compliance.explain");
  const info =
    infoKey && te.has(`${infoKey}.what`) ? (
      <MetricInfo
        title={title}
        what={te(`${infoKey}.what`)}
        how={te.has(`${infoKey}.how`) ? te(`${infoKey}.how`) : undefined}
        source={te.has(`${infoKey}.source`) ? te(`${infoKey}.source`) : undefined}
      />
    ) : null;
  return (
    <Card className={`flex h-full min-w-0 flex-col ${className ?? ""}`}>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="flex items-center gap-1 text-[0.78rem] font-medium">
          <span>{title}</span>
          {info}
        </CardTitle>
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
      <path
        d={d}
        fill="none"
        stroke="var(--tessera-fg-success)"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
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
  infoKey,
  onDrill,
  drillLabel,
}: {
  label: string;
  value: string;
  unit?: string;
  sub?: string;
  tone?: string;
  series?: number[];
  delta?: number | null;
  deltaUpIsGood?: boolean;
  /** Key under compliance.explain — renders a ⓘ "what is this / how computed". */
  infoKey?: string;
  /** Makes the whole tile a drill-down (jump to its detail tab) with a ↗ affordance.
   * Overlay-button pattern so the inner ⓘ never triggers the drill. */
  onDrill?: () => void;
  drillLabel?: string;
}) {
  const dec0 = useDecimalFormat(0);
  const tc = useTranslations("compliance");
  const te = useTranslations("compliance.explain");
  const showDelta = delta != null && Math.abs(delta) >= 0.005;
  const up = (delta ?? 0) > 0;
  const deltaGood = up === (deltaUpIsGood ?? true);
  const z = onDrill ? "pointer-events-none relative z-20" : "";
  return (
    <Card
      className={`group relative flex flex-col gap-0.5 p-3 ${
        onDrill ? "cursor-pointer transition-colors hover:border-[var(--tessera-green)]/40" : ""
      }`}
    >
      {onDrill ? (
        <button
          type="button"
          onClick={onDrill}
          aria-label={drillLabel}
          className="absolute inset-0 z-10 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--tessera-green)]/40"
        />
      ) : null}
      <div className={`flex items-center gap-1 text-xs text-[var(--muted-foreground)] ${z}`}>
        <span className="truncate">{label}</span>
        {infoKey ? (
          <span className={onDrill ? "pointer-events-auto ml-auto" : "ml-auto"}>
            <MetricInfo
              title={label}
              what={te(`${infoKey}.what`)}
              how={te(`${infoKey}.how`)}
              source={te.has(`${infoKey}.source`) ? te(`${infoKey}.source`) : undefined}
            />
          </span>
        ) : null}
      </div>
      <div
        className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"} ${z}`}
      >
        {value}
        {unit ? (
          <span className="text-base font-medium text-[var(--muted-foreground)]">{unit}</span>
        ) : null}
      </div>
      {showDelta ? (
        <div className={`flex items-center gap-1 text-xs tabular-nums ${z}`}>
          <span className={`whitespace-nowrap ${deltaGood ? GOOD : BAD}`}>
            {up ? "↗" : "↘"} {dec0(Math.abs((delta as number) * 100))} {tc("kpi.pts")}
          </span>
          <span className="truncate text-[var(--muted-foreground)]">{tc("kpi.vsPrev")}</span>
        </div>
      ) : sub ? (
        <div className={`truncate text-xs text-[var(--muted-foreground)] ${z}`}>{sub}</div>
      ) : null}
      {series && series.length > 1 ? <Spark values={series} /> : null}
      {onDrill ? (
        <ArrowUpRight className="pointer-events-none absolute right-2 bottom-2 z-20 h-3 w-3 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </Card>
  );
}

/** Stacked conformance bar (conformant / partial / non-conformant). */
function StackBar({ c, p, n }: { c: number; p: number; n: number }) {
  const total = c + p + n || 1;
  return (
    <div className="flex h-[4px] w-24 overflow-hidden rounded-full">
      <div style={{ width: `${(c / total) * 100}%`, background: "var(--tessera-fg-success)" }} />
      <div style={{ width: `${(p / total) * 100}%`, background: "var(--tessera-fg-warning)" }} />
      <div style={{ width: `${(n / total) * 100}%`, background: "var(--tessera-fg-danger)" }} />
    </div>
  );
}

/** Evidence-completeness donut. */
function EvidenceDonut({ completeness }: { completeness: number }) {
  const R = 30;
  const C = 2 * Math.PI * R;
  const tone =
    completeness >= 0.9
      ? "var(--tessera-fg-success)"
      : completeness >= 0.7
        ? "var(--tessera-fg-warning)"
        : "var(--tessera-fg-danger)";
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

export function ComplianceDashboard({ agentScope }: { agentScope?: ReactNode }) {
  const tc = useTranslations("compliance");
  const [activeTab, setActiveTab] = useUrlBackedView(TABS, "overview");
  const temporal = useTemporalState();
  const { historyMode } = temporal;
  const railTimeline = useRailTimeline();
  const locale = useLocale();
  // The window LENGTH, from the header's period selector. This page SHOWS that selector, so
  // its posture must be the posture over the selected period — a control that steers nothing
  // is worse than no control, because it is read as if it did.
  const period = useWindowStore((st) => st.period);
  const q = useQuery({
    queryKey: ["compliance", locale, period],
    queryFn: ({ signal }) => fetchCompliance(locale, signal, period),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL,
  });
  const d = q.data;

  if (!d?.available) {
    // The per-agent context does not depend on the posture read (different store): a
    // proven table must not hide behind an unrelated outage. The posture card still
    // states its own unavailability — found live with ClickHouse down, the whole page
    // collapsed to one sentence while the per-agent facts were sitting in Postgres.
    return (
      <div className="flex flex-col gap-2.5">
        {agentScope ? <div className="-mt-0.5">{agentScope}</div> : null}
        <Card>
          <CardContent className="py-10 text-center text-sm text-[var(--muted-foreground)]">
            {q.isLoading ? tc("loading") : tc("unavailable")}
          </CardContent>
        </Card>
      </div>
    );
  }

  const fwLabel = (code: string) => d.frameworks?.find((f) => f.code === code)?.label ?? code;
  const evTotal = (d.evidence_valid ?? 0) + (d.evidence_missing ?? 0) + (d.evidence_blocking ?? 0);
  // Real posture trend from the durable quality-score log (sparkline + delta).
  const trend = d.score_series ?? [];

  return (
    <div className="flex flex-col gap-2.5">
      {/* SR-01 rail LEADS — directly beneath the SLO breach alert the page renders above
          the dashboard (user feedback); then the tabs and the per-agent context. */}
      <SignalCommandBar
        temporal={temporal}
        timeline={railTimeline.data}
        liveStatus={tc("status.realtime")}
      />

      {/* tab bar */}
      <TabStrip
        accent="green"
        active={activeTab}
        onChange={setActiveTab}
        items={TABS.map((t) => ({
          key: t,
          label: tc(`tabs.${t}`),
          icon: TAB_ICONS[t],
        }))}
      />

      {/* Agent-scope context (Vue par agent) sits below the rail + tabs. */}
      {agentScope ? <div className="-mt-0.5">{agentScope}</div> : null}

      {activeTab !== "overview" && d.tabs?.[activeTab] ? (
        <>
          {/* The seven catalogue tabs are governance fixtures (compliance_tabs.py calls itself
              "fixed, deterministic fixture data"). The overview below is derived from real
              runtime signals and carries no notice — the registry drives which is which. */}
          <ProvenanceNotice signalId="compliance_catalog" />
          <CatalogTabView tab={d.tabs[activeTab]} footer={<TabFooter tc={tc} />} />
        </>
      ) : (
        <>
          <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="flex min-w-0 flex-col gap-2">
              {/* A. Posture réglementaire */}
              <Zone label={tc("sec.actual")}>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
                  <Kpi
                    label={tc("kpi.score")}
                    infoKey="score"
                    value={showNumber(d.score)}
                    unit="/100"
                    sub={tc("kpi.scoreSub")}
                    tone={toneFor(d.score, (v) => v < 80, TONE_WARN)}
                    series={trend}
                    delta={d.score_delta}
                    deltaUpIsGood
                  />
                  <Kpi
                    label={tc("kpi.obligations")}
                    infoKey="obligations"
                    onDrill={() => setActiveTab("obligations")}
                    drillLabel={tc("tabs.obligations")}
                    value={`${d.n_applied ?? 0}`}
                    unit={`/${d.n_obligations ?? 0}`}
                    sub={`${Math.round(((d.n_applied ?? 0) / (d.n_obligations || 1)) * 100)}%`}
                    tone={GOOD}
                    series={trend}
                  />
                  <Kpi
                    label={tc("kpi.conformant")}
                    infoKey="conformant"
                    onDrill={() => setActiveTab("evaluations")}
                    drillLabel={tc("tabs.evaluations")}
                    value={`${d.n_conformant ?? 0}`}
                    unit={`/${d.n_controls ?? 0}`}
                    sub={`${Math.round(((d.n_conformant ?? 0) / (d.n_controls || 1)) * 100)}%`}
                    tone={GOOD}
                    series={trend}
                  />
                  <Kpi
                    label={tc("kpi.partial")}
                    infoKey="partial"
                    onDrill={() => setActiveTab("evaluations")}
                    drillLabel={tc("tabs.evaluations")}
                    value={`${d.n_partial ?? 0}`}
                    sub={`${Math.round(((d.n_partial ?? 0) / (d.n_controls || 1)) * 100)}%`}
                    tone={WARN}
                  />
                  <Kpi
                    label={tc("kpi.nonConformant")}
                    infoKey="nonConformant"
                    onDrill={() => setActiveTab("evaluations")}
                    drillLabel={tc("tabs.evaluations")}
                    value={showNumber(d.n_non_conformant)}
                    sub={showNumber(
                      d.n_non_conformant,
                      (v) => `${Math.round((v / (d.n_controls || 1)) * 100)}%`,
                    )}
                    tone={toneFor(d.n_non_conformant, (v) => v > 0, TONE_BAD)}
                  />
                  <Kpi
                    label={tc("kpi.residual")}
                    infoKey="residual"
                    value={`${d.n_residual_risk ?? 0}`}
                    sub={tc("kpi.residualSub")}
                    tone={WARN}
                  />
                  <Kpi
                    label={tc("kpi.deadlines")}
                    infoKey="deadlines"
                    onDrill={() => setActiveTab("obligations")}
                    drillLabel={tc("tabs.obligations")}
                    value={showNumber(d.n_critical_deadlines)}
                    sub={tc("kpi.deadlinesSub")}
                    tone={toneFor(d.n_critical_deadlines, (v) => v > 0, TONE_BAD)}
                  />
                </div>
              </Zone>

              {/* B. Cartographie · obligations · evidence */}
              <Zone label={tc("sec.mapping")}>
                <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1.3fr)_minmax(0,1fr)]">
                  <Panel title={tc("panel.mapping")} infoKey="mapping">
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
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
                    </div>
                  </Panel>

                  <Panel
                    title={tc("panel.obligations", { n: d.obligations?.length ?? 0 })}
                    infoKey="obligTable"
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
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
                    </div>
                  </Panel>

                  <Panel title={tc("panel.evidence")} infoKey="evidence">
                    <div className="flex items-center gap-3">
                      <EvidenceDonut completeness={d.evidence_completeness ?? 0} />
                      <ul className="flex flex-col gap-1 text-xs">
                        <EvRow
                          color="var(--tessera-fg-success)"
                          label={tc("evidence.valid")}
                          value={d.evidence_valid ?? 0}
                        />
                        <EvRow
                          color="var(--tessera-fg-warning)"
                          label={tc("evidence.missing")}
                          value={d.evidence_missing ?? 0}
                        />
                        <EvRow
                          color="var(--tessera-fg-danger)"
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
                      onClick={() =>
                        downloadBlob(
                          "tessera-compliance-evidence.json",
                          "application/json",
                          JSON.stringify(
                            {
                              evidence_valid: d.evidence_valid ?? 0,
                              evidence_missing: d.evidence_missing ?? 0,
                              evidence_blocking: d.evidence_blocking ?? 0,
                              controls: d.controls ?? [],
                            },
                            null,
                            2,
                          ),
                        )
                      }
                      className="mt-2 h-7 w-full justify-center text-xs"
                    >
                      {tc("evidence.export")}
                    </Button>
                  </Panel>
                </div>
              </Zone>

              <BusinessLegalSignalsPanel rows={d.business_legal_signals ?? []} />

              {/* C. Contrôles · preuves manquantes · incidents */}
              <Zone label={tc("sec.controls")}>
                <div className="grid gap-2 lg:grid-cols-3">
                  <Panel
                    title={tc("panel.controls", { n: d.controls?.length ?? 0 })}
                    infoKey="controls"
                  >
                    <ul className="flex flex-col gap-1 text-xs">
                      {(d.controls ?? []).slice(0, 6).map((c) => (
                        <li key={c.id} className="flex items-center gap-2">
                          <Truncate full={c.name} className="min-w-0 flex-1">
                            {c.name}
                          </Truncate>
                          <Badge tone={STATUS_BADGE[c.status] ?? "neutral"}>
                            {tc(`status.${c.status}`)}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  </Panel>

                  <Panel title={tc("panel.missing")} infoKey="missing">
                    <ul className="flex flex-col gap-1 text-xs">
                      {(d.controls ?? [])
                        .filter((c) => c.status !== "conformant")
                        .slice(0, 7)
                        .map((c) => (
                          <li key={c.id} className="flex items-center justify-between gap-2">
                            <Truncate
                              full={c.evidence_id}
                              className="min-w-0 flex-1 font-mono text-xs"
                            >
                              {c.evidence_id}
                            </Truncate>
                            <span className="shrink-0 text-[var(--muted-foreground)]">
                              {fwLabel(c.framework)}
                            </span>
                          </li>
                        ))}
                    </ul>
                  </Panel>

                  <Panel title={tc("panel.incidents")} infoKey="incidents">
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
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
                              <td className="py-1 pr-2 font-mono text-[var(--tessera-green)]">
                                {nc.id}
                              </td>
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
                    </div>
                  </Panel>
                </div>
              </Zone>
            </div>

            <ComplianceRail
              obligations={d.obligations ?? []}
              nc={d.non_conformities ?? []}
              fwLabel={fwLabel}
              onExportReport={() =>
                downloadBlob(
                  "tessera-compliance.json",
                  "application/json",
                  JSON.stringify(d, null, 2),
                )
              }
            />
          </div>

          {/* footer */}
          <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-xs text-[var(--muted-foreground)]">
            <Chip
              icon={ShieldCheck}
              label={tc("status.chain")}
              tone="text-[var(--tessera-green)]"
            />
            <Chip icon={ScrollText} label={tc("status.truth")} />
            <Chip icon={FileCheck2} label={tc("status.env")} />
          </div>
        </>
      )}
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
        <Truncate full={o.name} className="max-w-[12rem]">
          {o.name}
        </Truncate>
        <span className="text-xs text-[var(--muted-foreground)]">{fwLabel(o.framework)}</span>
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

function BusinessLegalSignalsPanel({ rows }: { rows: BusinessLegalSignal[] }) {
  const tc = useTranslations("compliance");
  const tb = useTranslations("businessSignal");
  return (
    <Zone label={tc("sec.businessLegal")}>
      <Panel title={tc("panel.businessLegal", { n: rows.length })} infoKey="businessLegal">
        {rows.length === 0 ? (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            {tc("businessSignals.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table data-premium-table="true" className="w-full table-fixed text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                  <th className="w-[22%] py-1 pr-2 font-medium">{tc("businessSignals.agent")}</th>
                  <th className="w-[34%] py-1 pr-2 font-medium">{tc("businessSignals.signal")}</th>
                  <th className="w-[14%] py-1 pr-2 font-medium">{tc("businessSignals.value")}</th>
                  <th className="w-[16%] py-1 pr-2 font-medium">{tc("businessSignals.status")}</th>
                  <th className="w-[14%] py-1 font-medium">{tc("businessSignals.source")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const label = tb.has(row.key) ? tb(row.key) : row.key;
                  const value =
                    typeof row.value_pct === "number" ? `${Math.round(row.value_pct)}%` : "—";
                  return (
                    <tr
                      key={`${row.agent_id}.${row.key}`}
                      className="border-b border-[var(--border)]/50"
                    >
                      <td className="py-1 pr-2">
                        <Link href={row.href} className="truncate text-[var(--tessera-green)]">
                          {row.agent_name}
                        </Link>
                      </td>
                      <td className="py-1 pr-2">
                        <Truncate full={label}>{label}</Truncate>
                      </td>
                      <td className="py-1 pr-2 tabular-nums">{value}</td>
                      <td className="py-1 pr-2">
                        <Badge tone={BUSINESS_STATUS_BADGE[row.status] ?? "neutral"}>
                          {tc(`businessSignals.statusValue.${row.status}`)}
                        </Badge>
                      </td>
                      <td className="py-1 text-[var(--muted-foreground)]">
                        <Truncate full={row.source}>{row.source}</Truncate>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </Zone>
  );
}

/** Shared footer for the catalogue tabs (référentiel · revue · preuves · source). */
function TabFooter({ tc }: { tc: ReturnType<typeof useTranslations<"compliance">> }) {
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-xs text-[var(--muted-foreground)]">
      <Chip icon={ScrollText} label={tc("footer.reference")} />
      <Chip icon={CalendarClock} label={tc("footer.lastReview")} />
      <Chip icon={FileCheck2} label={tc("footer.validProofs")} />
      <Chip icon={BookText} label={tc("footer.source")} />
      <Chip icon={ShieldCheck} label={tc("footer.audit")} tone="text-[var(--tessera-green)]" />
    </div>
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
  onExportReport,
}: {
  obligations: ComplianceObligation[];
  nc: NonConformity[];
  fwLabel: (c: string) => string;
  onExportReport: () => void;
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
          <CardContent className="flex items-center justify-between gap-2 text-xs">
            {/* The compliance payload carries no evaluation date yet — say so, never
                invent one (the previous hardcoded "11/06/2026" was a lie). */}
            <span className="text-[var(--muted-foreground)]">{tc("rail.lastEvalMissing")}</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{tc("rail.deadlines")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {obligations.slice(0, 4).map((o) => (
              <div key={o.name} className="flex items-center gap-2 text-xs">
                <Truncate full={o.name} className="min-w-0 flex-1">
                  {o.name}
                </Truncate>
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
              <p className="text-xs text-[var(--muted-foreground)]">{tc("rail.noNc")}</p>
            ) : (
              criticalNc.slice(0, 4).map((n) => (
                <div key={n.id} className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-[var(--tessera-green)]">{n.id}</span>
                  <Truncate
                    full={n.title}
                    className="min-w-0 flex-1 text-[var(--muted-foreground)]"
                  >
                    {n.title}
                  </Truncate>
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
                className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-xs"
              >
                <CalendarClock className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
                <Truncate full={o.name} className="min-w-0 flex-1">
                  {o.name}
                </Truncate>
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
            {(
              [
                { key: "qaEvidence", icon: FileCheck2, href: "/prouver/evidence-store" },
                { key: "qaRemediation", icon: ListChecks, href: "/surveiller/amelioration" },
                { key: "qaReport", icon: FileDown, onClick: onExportReport },
                { key: "qaRegistry", icon: BookText },
              ] as { key: string; icon: LucideIcon; href?: Route; onClick?: () => void }[]
            ).map((a) => {
              const cls =
                "flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]";
              if (a.href) {
                return (
                  <Link key={a.key} href={a.href} className={cls}>
                    <a.icon className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{tc(`rail.${a.key}`)}</span>
                  </Link>
                );
              }
              if (a.onClick) {
                return (
                  <button key={a.key} type="button" onClick={a.onClick} className={cls}>
                    <a.icon className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{tc(`rail.${a.key}`)}</span>
                  </button>
                );
              }
              // No processing registry exists yet — honest disabled state, never a silent no-op.
              return (
                <button
                  key={a.key}
                  type="button"
                  disabled
                  title={tc("rail.notWired")}
                  className="flex cursor-not-allowed items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs text-[var(--muted-foreground)] opacity-60"
                >
                  <a.icon className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{tc(`rail.${a.key}`)}</span>
                </button>
              );
            })}
          </CardContent>
        </Card>

        <Link
          href="/prouver/evidence-store"
          className="inline-flex h-8 w-full items-center justify-center gap-2 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[var(--tessera-fg-accent)] transition-colors hover:bg-[#4c3fb0]/60"
        >
          {tc("rail.evidenceCta")}
        </Link>
      </div>
    </aside>
  );
}

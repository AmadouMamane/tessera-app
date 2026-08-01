"use client";

import {
  ArrowUpRight,
  BookCheck,
  ChevronRight,
  Database,
  ListChecks,
  ListPlus,
  Lock,
  RefreshCw,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { AuthorityLabel } from "@/components/cockpit/authority-label";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricKpi } from "@/components/observability/evolution-chart";
import type { SignalRow } from "@/components/observability/signals-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Truncate } from "@/components/ui/truncate";
import type {
  Calibration,
  FailedCasesReport,
  IntentReport,
  JudgeDrift,
  LocalizationReport,
  MetricPairs,
  ModelComparison,
  PredictorEvaluation,
  Regression,
  RegressionRisk,
  ReleaseStatus,
  RunRegistry,
  ScoreSeries,
  WhatChanged,
} from "@/lib/api/schemas";

/** Overview target tabs that a recommended action can route to. */
export type OverviewTab = "overview" | "signals" | "runs" | "failed" | "models" | "judge";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";

/** A translucent sub-card used inside the zone bands (same shape as the
 * Sécurité & privacy `Panel`): every cockpit zone is a banded section grouping
 * real cards, not flat sections. */
function SubPanel({
  title,
  info,
  action,
  children,
  className,
}: {
  title: string;
  /** Optional ⓘ explainer next to the panel title. */
  info?: React.ReactNode;
  /** Optional header-right affordance (e.g. a drill-down link). */
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={`flex h-full min-w-0 flex-col ${className ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1 text-[0.78rem] font-medium">
          <span className="min-w-0 truncate">{title}</span>
          {info}
        </CardTitle>
      </CardHeader>
      {/* Drill-down sits in the FOOTER, not the header: these zone sub-cards are
          narrow, and a header-right link squeezes the title to an ellipsis. */}
      <CardContent className="flex flex-1 flex-col">
        {children}
        {action ? <div className="mt-auto pt-2">{action}</div> : null}
      </CardContent>
    </Card>
  );
}

/** A compact "see → {tab}" drill-down used in a sub-card header/footer. */
function CardTabLink({
  onOpen,
  tab,
  label,
}: {
  onOpen: (t: OverviewTab) => void;
  tab: OverviewTab;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(tab)}
      className="inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap text-[0.62rem] text-[var(--tessera-green)] hover:underline"
    >
      {label}
      <ChevronRight className="h-3 w-3" />
    </button>
  );
}

/** Compact, overflow-proof case reference for the dense zone-B list
 * (e.g. "01_prompt_injection" → "#01"). Falls back to the first token. */
function shortCaseRef(caseId: string): string {
  const numeric = caseId.match(/^\d+/)?.[0];
  if (numeric) return `#${numeric}`;
  const token = caseId.split(/[_-]/)[0] ?? caseId;
  return token.slice(0, 6).toUpperCase();
}

/** A ⓘ for a quality KPI tile, reading quality.explain.<k>.{what,how,source}. */
function KpiInfo({ title, k }: { title: string; k: string }) {
  const te = useTranslations("quality.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

/** A plain value KPI tile (no time series), with an optional tone + hint + ⓘ + drill. */
function ValueKpi({
  label,
  value,
  tone,
  hint,
  info,
  onDrill,
  drillLabel,
}: {
  label: string;
  value: string;
  tone?: string;
  hint?: string;
  info?: React.ReactNode;
  /** Makes the whole tile a drill-down (jump to the detail tab) with a ↗ affordance.
   * Overlay-button pattern so the inner ⓘ never triggers the drill. */
  onDrill?: () => void;
  drillLabel?: string;
}) {
  return (
    <Card
      className={`group relative flex flex-col gap-0.5 p-2 ${
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
      <div
        className={`flex items-center gap-1 text-[0.7rem] leading-tight text-[var(--muted-foreground)] ${
          onDrill ? "pointer-events-none relative z-20" : ""
        }`}
      >
        <span className="min-w-0 truncate">{label}</span>
        {info ? <span className={onDrill ? "pointer-events-auto" : undefined}>{info}</span> : null}
      </div>
      <div
        className={`text-lg font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"} ${
          onDrill ? "pointer-events-none relative z-20" : ""
        }`}
      >
        {value}
      </div>
      {hint ? (
        <div
          className={`text-[0.6rem] text-[var(--muted-foreground)] ${
            onDrill ? "pointer-events-none relative z-20" : ""
          }`}
        >
          {hint}
        </div>
      ) : null}
      {onDrill ? (
        <ArrowUpRight className="pointer-events-none absolute right-1.5 bottom-1.5 z-20 h-3 w-3 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </Card>
  );
}

/** A tiny inline sparkline of a metric's bucket means (État actuel, image 00). */
function MiniSpark({ series }: { series: ScoreSeries | undefined }) {
  const pts = (series?.buckets ?? []).map((b) => b.mean).filter((m): m is number => m != null);
  if (pts.length < 2) return null;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const span = max - min || 1;
  const w = 96;
  const h = 22;
  const d = pts
    .map((v, i) => {
      const x = (i / (pts.length - 1)) * w;
      const y = h - ((v - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const rising = (pts.at(-1) ?? 0) >= (pts[0] ?? 0);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-6 w-24 shrink-0" aria-hidden="true">
      <path
        d={d}
        fill="none"
        stroke={rising ? "var(--tessera-fg-success)" : "var(--tessera-fg-danger)"}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** The 8-tile headline KPI strip of the Vue d'ensemble (reference image 00). */
export function OverviewKpis({
  sloPct,
  faithfulness,
  grounding,
  hallucination,
  nonRegression,
  nRegressions,
  kappa,
  evaluatedCount,
  loading,
  onOpen,
}: {
  sloPct: number | null;
  faithfulness: ScoreSeries | undefined;
  grounding: ScoreSeries | undefined;
  hallucination: ScoreSeries | undefined;
  nonRegression: number | null;
  nRegressions: number | null;
  kappa: number | null;
  evaluatedCount: number | null;
  loading: boolean;
  /** Makes each KPI tile drill into its detail tab (↗). */
  onOpen?: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const scoreTone = sloPct == null ? MUTED : sloPct >= 80 ? GOOD : sloPct >= 60 ? WARN : BAD;
  const nonRegTone =
    nonRegression == null ? MUTED : nonRegression >= 0.9 ? GOOD : nonRegression >= 0.7 ? WARN : BAD;
  const regTone = nRegressions == null ? MUTED : nRegressions === 0 ? GOOD : WARN;
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4 2xl:grid-cols-8">
      <ValueKpi
        label={tq("exec.kpi.scoreGlobal")}
        value={sloPct == null ? "—" : `${sloPct}`}
        tone={scoreTone}
        hint="/100"
        info={<KpiInfo title={tq("exec.kpi.scoreGlobal")} k="scoreGlobal" />}
        onDrill={onOpen ? () => onOpen("signals") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <MetricKpi
        label={tq("metrics.faithfulness")}
        series={faithfulness}
        loading={loading}
        info={<KpiInfo title={tq("metrics.faithfulness")} k="faithfulness" />}
        onDrill={onOpen ? () => onOpen("signals") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <MetricKpi
        label={tq("metrics.grounding")}
        series={grounding}
        loading={loading}
        info={<KpiInfo title={tq("metrics.grounding")} k="grounding" />}
        onDrill={onOpen ? () => onOpen("signals") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <ValueKpi
        label={tq("exec.kpi.nonRegression")}
        value={nonRegression == null ? "—" : `${Math.round(nonRegression * 100)}%`}
        tone={nonRegTone}
        info={<KpiInfo title={tq("exec.kpi.nonRegression")} k="nonRegression" />}
        onDrill={onOpen ? () => onOpen("runs") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <MetricKpi
        label={tq("metrics.hallucination")}
        series={hallucination}
        loading={loading}
        info={<KpiInfo title={tq("metrics.hallucination")} k="hallucination" />}
        onDrill={onOpen ? () => onOpen("failed") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <ValueKpi
        label={tq("exec.kpi.regressionsOpen")}
        value={nRegressions == null ? "—" : String(nRegressions)}
        tone={regTone}
        info={<KpiInfo title={tq("exec.kpi.regressionsOpen")} k="regressionsOpen" />}
        onDrill={onOpen ? () => onOpen("runs") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <ValueKpi
        label={tq("exec.kpi.judgeKappa")}
        value={kappa == null ? "—" : kappa.toFixed(2)}
        info={<KpiInfo title={tq("exec.kpi.judgeKappa")} k="judgeKappa" />}
        onDrill={onOpen ? () => onOpen("judge") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <ValueKpi
        label={tq("exec.kpi.casEval")}
        value={evaluatedCount == null ? "—" : String(evaluatedCount)}
        info={<KpiInfo title={tq("exec.kpi.casEval")} k="casEval" />}
        onDrill={onOpen ? () => onOpen("runs") : undefined}
        drillLabel={tq("seeDetail")}
      />
    </div>
  );
}

/** "A. État actuel" — narrow status column: global score, failing/alert counts,
 * release impact + blocked state, and the period-over-period evolution (image 00). */
export function EtatActuel({
  summary,
  release,
  evolutionDelta,
  scorePct,
  series,
}: {
  summary: { ok: number; warn: number; crit: number; na: number; total: number };
  release: ReleaseStatus | undefined;
  evolutionDelta: number | null;
  scorePct: number | null;
  series: ScoreSeries | undefined;
}) {
  const tq = useTranslations("quality");
  const nReg = release?.n_regressions ?? null;
  const impact = nReg == null ? null : nReg === 0 ? "low" : nReg <= 2 ? "medium" : "high";
  const blocked = (nReg ?? 0) > 0;
  const current = release?.current ?? null;
  const evoPts = evolutionDelta == null ? null : Math.round(evolutionDelta * 100);
  const evoTone = evoPts == null ? MUTED : evoPts > 0 ? GOOD : evoPts < 0 ? BAD : MUTED;
  const scoreTone = scorePct == null ? MUTED : scorePct >= 80 ? GOOD : scorePct >= 60 ? WARN : BAD;
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 pt-3 text-xs">
        <Row
          label={tq("exec.etat.globalQuality")}
          info={<KpiInfo title={tq("exec.etat.globalQuality")} k="scoreGlobal" />}
        >
          <span className={`tabular-nums font-semibold ${scoreTone}`}>
            {scorePct == null ? "—" : `${scorePct}/100`}
          </span>
        </Row>
        <Row label={tq("exec.etat.failing")}>
          <span className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${summary.crit > 0 ? "bg-red-500" : "bg-[var(--muted-foreground)]"}`}
            />
            <span className={summary.crit > 0 ? BAD : MUTED}>
              {summary.crit} {tq("signalsTable.status.crit").toLowerCase()}
            </span>
          </span>
        </Row>
        <Row label={tq("exec.etat.alert")}>
          <span className="flex items-center gap-1.5">
            <span
              className={`h-2 w-2 rounded-full ${summary.warn > 0 ? "bg-amber-500" : "bg-[var(--muted-foreground)]"}`}
            />
            <span className={summary.warn > 0 ? WARN : MUTED}>
              {summary.warn} {tq("signalsTable.status.warn").toLowerCase()}
            </span>
          </span>
        </Row>
        <Row label={tq("exec.etat.impact")}>
          {impact == null ? (
            <span className={MUTED}>—</span>
          ) : (
            <Badge
              tone={impact === "high" ? "danger" : impact === "medium" ? "warning" : "success"}
            >
              {tq(`exec.etat.${impact}`)}
            </Badge>
          )}
        </Row>
        <div className="flex items-center justify-between gap-2 border-t border-[var(--tessera-border)] pt-1.5">
          <span className="text-[var(--muted-foreground)]">{tq("exec.etat.releaseLabel")}</span>
          {current ? (
            <span className="flex items-center gap-1.5">
              <span className="font-mono tabular-nums">{current.version}</span>
              <Badge tone={blocked ? "danger" : "success"}>
                {blocked ? tq("rr.blocked") : tq("rr.inProd")}
              </Badge>
            </span>
          ) : (
            <span className={MUTED}>—</span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-[var(--tessera-border)] pt-1.5">
          <div className="flex min-w-0 flex-col">
            <span className="text-[var(--muted-foreground)]">
              {tq("exec.etat.evolutionVsPrev")}
            </span>
            <span className={`text-base font-semibold tabular-nums ${evoTone}`}>
              {evoPts == null ? "—" : `${evoPts >= 0 ? "+" : ""}${evoPts} pts`}
            </span>
          </div>
          <MiniSpark series={series} />
        </div>
      </CardContent>
    </Card>
  );
}

function Row({
  label,
  children,
  info,
}: { label: string; children: React.ReactNode; info?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="flex items-center gap-1 text-[var(--muted-foreground)]">
        {label}
        {info}
      </span>
      {children}
    </div>
  );
}

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  ok: "success",
  warn: "warning",
  crit: "danger",
  na: "neutral",
};
const RANK: Record<string, number> = { crit: 0, warn: 1, ok: 2, na: 3 };

/** "Signaux qualité — top problèmes": the failing/at-risk signals only (image 00). */
export function TopProblems({ rows, limit = 6 }: { rows: SignalRow[]; limit?: number }) {
  const tq = useTranslations("quality");
  const problems = rows
    .filter((r) => r.status === "crit" || r.status === "warn")
    .sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9))
    .slice(0, limit);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("exec.topProblems")}</CardTitle>
      </CardHeader>
      <CardContent>
        {problems.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {tq("exec.noProblems")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.signal")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.status")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("signalsTable.cols.score")}</th>
                  <th className="py-2 font-medium">{tq("signalsTable.cols.threshold")}</th>
                </tr>
              </thead>
              <tbody>
                {problems.map((r) => (
                  <tr key={r.key} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-4 font-medium">{r.name}</td>
                    <td className="py-2 pr-4">
                      <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>
                        {tq(`signalsTable.status.${r.status}`)}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4 font-semibold tabular-nums">{r.score}</td>
                    <td className="py-2 tabular-nums text-[var(--muted-foreground)]">
                      {r.threshold}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const VERDICT_COLOR: Record<string, string> = {
  best: "var(--tessera-fg-success)",
  balanced: "var(--tessera-fg-info)",
  economic: "var(--tessera-fg-success)",
  avoid: "var(--tessera-fg-danger)",
};

function rateColor(r: number): string {
  return r >= 0.8
    ? "var(--tessera-fg-success)"
    : r >= 0.5
      ? "var(--tessera-fg-warning)"
      : "var(--tessera-fg-danger)";
}

/** "Diagnostic racine (probable)" — what changed / probable causes / impact (image 00). */
export function RootCauseDiagnostic({
  whatChanged,
  regressions,
}: {
  whatChanged: WhatChanged | undefined;
  regressions: Regression[];
}) {
  const tq = useTranslations("quality");
  const wc = whatChanged;
  if (!wc?.available) {
    return (
      <SubPanel title={tq("charts.diagnostic")}>
        <p className="py-4 text-center text-sm text-[var(--muted-foreground)]">
          {tq("charts.noDiag")}
        </p>
      </SubPanel>
    );
  }
  const changes = wc.changes ?? [];
  const docsAdded = wc.docs_added ?? [];
  const docsRemoved = wc.docs_removed ?? [];
  const delta = wc.score_delta ?? null;
  const causes: string[] = [];
  for (const c of changes) causes.push(`${tq("charts.change")} : ${c.field}`);
  if (docsAdded.length || docsRemoved.length) {
    causes.push(`${tq("charts.corpusChanged")} (+${docsAdded.length}/−${docsRemoved.length})`);
  }
  if (wc.regressed) causes.push(tq("charts.scoreRegressed"));
  return (
    <SubPanel title={tq("charts.diagnostic")}>
      <div className="flex flex-col gap-2 text-[0.7rem]">
        <div
          // One column on a phone, two from 640px. And `min-w-0` on the items:
          // a grid item defaults to `min-width:auto`, so a card whose content has a
          // wide min-content (a chart, a long unbreakable label) refuses to shrink
          // and pushes its column past the viewport — measured at 390px, the two
          // chart cards sat 324px wide in a 278px column and were clipped.
          className="grid grid-cols-1 gap-3 sm:grid-cols-2 [&>*]:min-w-0"
        >
          <section className="min-w-0">
            <h4 className="mb-1 font-semibold text-[var(--muted-foreground)]">
              {tq("charts.whatChangedTitle")}
            </h4>
            <ul className="flex flex-col gap-0.5">
              {changes.map((c) => (
                <li key={c.field} className="truncate font-mono">
                  {c.field}: {c.before.slice(0, 6)} → {c.after.slice(0, 6)}
                </li>
              ))}
              {docsAdded.length ? (
                <li className="text-[var(--tessera-fg-success)]">+{docsAdded.length} docs</li>
              ) : null}
              {docsRemoved.length ? (
                <li className="text-[var(--tessera-fg-danger)]">−{docsRemoved.length} docs</li>
              ) : null}
            </ul>
          </section>
          <section className="min-w-0">
            <h4 className="mb-1 font-semibold text-[var(--muted-foreground)]">
              {tq("charts.causes")}
            </h4>
            <ul className="flex flex-col gap-0.5 text-[var(--muted-foreground)]">
              {causes.map((c) => (
                <li key={c} className="truncate">
                  • {c}
                </li>
              ))}
            </ul>
          </section>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-[var(--tessera-border)] pt-1.5">
          <span className="font-semibold text-[var(--muted-foreground)]">
            {tq("charts.impact")}
          </span>
          {delta != null ? (
            <Badge tone={delta >= 0 ? "success" : "danger"} className="tabular-nums">
              {delta >= 0 ? "+" : ""}
              {Math.round(delta * 100)} pts
            </Badge>
          ) : null}
          {regressions.map((r) => (
            <span key={r.model} className="text-[var(--tessera-fg-danger)]">
              {r.model} {Math.round(r.prev_rate * 100)}→{Math.round(r.last_rate * 100)}%
            </span>
          ))}
        </div>
      </div>
    </SubPanel>
  );
}

/** "D. Actions recommandées" — six governed actions, each carrying the required
 * role + a link into the relevant tab, plus the evidence-pack link (image 00). */
export function RecommendedActions({
  regressions,
  failed,
  onOpen,
  onEvidence,
}: {
  regressions: Regression[];
  failed: FailedCasesReport | undefined;
  onOpen: (tab: OverviewTab) => void;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const failedTotal = failed?.n ?? null;
  const actions: {
    key: string;
    icon: typeof BookCheck;
    label: string;
    role: "operator" | "admin";
    dual?: boolean;
    ctx: string | null;
    target: OverviewTab;
  }[] = [
    {
      key: "playbook",
      icon: BookCheck,
      label: tq("reco.playbook"),
      role: "operator",
      ctx: null,
      target: "failed",
    },
    {
      key: "corpus",
      icon: Database,
      label: tq("reco.corpus"),
      role: "operator",
      ctx: null,
      target: "signals",
    },
    {
      key: "rerun",
      icon: RefreshCw,
      label: tq("reco.rerun"),
      role: "operator",
      ctx: null,
      target: "runs",
    },
    {
      key: "curate",
      icon: ListPlus,
      label: tq("reco.curate"),
      role: "operator",
      ctx: failedTotal != null ? `${failedTotal}` : null,
      target: "failed",
    },
    {
      key: "catalog",
      icon: ListChecks,
      label: tq("reco.catalog"),
      role: "admin",
      ctx: null,
      target: "signals",
    },
    {
      key: "block",
      icon: Lock,
      label: tq("reco.block"),
      role: "admin",
      dual: true,
      ctx: regressions.length > 0 ? `${regressions.length}` : null,
      target: "models",
    },
  ];
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 pt-3">
        {actions.map((a) => (
          <button
            key={a.key}
            type="button"
            onClick={() => onOpen(a.target)}
            className="group flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-left text-[0.7rem] transition-colors hover:border-[var(--tessera-border-strong)] hover:bg-[var(--tessera-muted)]"
          >
            <a.icon className="h-3 w-3 shrink-0 text-[var(--muted-foreground)]" />
            <span className="min-w-0 flex-1 truncate">{a.label}</span>
            {a.ctx ? (
              <span className="shrink-0 tabular-nums text-[0.6rem] text-[var(--muted-foreground)]">
                {a.ctx}
              </span>
            ) : null}
            <Badge tone={a.role === "admin" ? "warning" : "success"} className="px-1 text-[0.6rem]">
              <AuthorityLabel authority={a.role === "admin" ? "Admin+" : "Operator+"} />
            </Badge>
          </button>
        ))}
        <button
          type="button"
          onClick={onEvidence}
          className="mt-0.5 inline-flex items-center gap-1 self-start text-[0.7rem] text-[var(--tessera-green)] hover:underline"
        >
          {tq("reco.seeEvidence")}
          <ChevronRight className="h-3 w-3" />
        </button>
      </CardContent>
    </Card>
  );
}

/** "Coût évaluation vs Qualité" scatter from the model comparison (image 00). */
export function CostQualityScatter({
  data,
  loading,
}: {
  data: ModelComparison | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const models = data?.models ?? [];
  const maxCost = Math.max(0.01, ...models.map((m) => m.est_cost_eur ?? 0));
  const H = 56;
  const top = 4;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("charts.costQuality")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !data ? (
          <Skeleton className="h-32 w-full" />
        ) : (
          <>
            <div className="relative h-16 w-full">
              <svg
                viewBox={`0 0 100 ${H + top * 2}`}
                preserveAspectRatio="none"
                className="h-full w-full"
                aria-hidden="true"
              >
                {[0, 0.5, 1].map((g) => (
                  <line
                    key={g}
                    x1={0}
                    x2={100}
                    y1={top + (1 - g) * H}
                    y2={top + (1 - g) * H}
                    stroke="var(--tessera-border)"
                    strokeWidth={0.3}
                  />
                ))}
                {models.map((m) => (
                  <circle
                    key={m.model}
                    cx={2 + ((m.est_cost_eur ?? 0) / maxCost) * 96}
                    cy={top + (1 - m.pass_rate) * H}
                    r={1.8}
                    fill={VERDICT_COLOR[m.verdict] ?? "var(--tessera-text-muted)"}
                  />
                ))}
              </svg>
            </div>
            <div className="mt-0.5 flex justify-between text-[0.6rem] text-[var(--muted-foreground)]">
              <span>↑ {tq("charts.qualityAxis")}</span>
              <span>{tq("charts.costAxis")} →</span>
            </div>
            <ul className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[0.6rem]">
              {models.map((m) => (
                <li
                  key={m.model}
                  className="flex items-center gap-1 text-[var(--muted-foreground)]"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{ background: VERDICT_COLOR[m.verdict] ?? "var(--tessera-text-muted)" }}
                  />
                  {m.model}
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Pass-rate of the most recent eval runs (real bars; the reference's per-release view). */
export function RunsBars({
  registry,
  loading,
}: {
  registry: RunRegistry | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const runs = [...(registry?.runs ?? [])].slice(0, 12).reverse();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("charts.runsBars")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !registry ? (
          <Skeleton className="h-40 w-full" />
        ) : runs.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("runs.empty")}
          </p>
        ) : (
          <div className="flex h-40 items-end gap-1">
            {runs.map((r) => (
              <div
                key={r.run_id}
                className="flex flex-1 flex-col items-center justify-end gap-1"
                title={`${r.model} · ${Math.round(r.pass_rate * 100)}%`}
              >
                <span className="text-[0.55rem] tabular-nums text-[var(--muted-foreground)]">
                  {Math.round(r.pass_rate * 100)}
                </span>
                <div
                  className="w-full rounded-t"
                  style={{
                    height: `${Math.max(2, r.pass_rate * 100)}%`,
                    background: rateColor(r.pass_rate),
                  }}
                />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** "Faithfulness vs Grounding" scatter from per-turn metric pairs (image 00). */
export function FaithGroundingScatter({
  pairs,
  loading,
  onOpen,
}: {
  pairs: MetricPairs | undefined;
  loading: boolean;
  onOpen?: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const points = pairs?.points ?? [];
  const H = 56;
  const top = 4;
  const bucketColor = (m: number) =>
    m >= 0.7
      ? "var(--tessera-fg-success)"
      : m >= 0.4
        ? "var(--tessera-fg-warning)"
        : "var(--tessera-fg-danger)";
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="flex min-w-0 items-center gap-1 text-sm">
          <span className="min-w-0 truncate">{tq("charts.faithGrounding")}</span>
          <KpiInfo title={tq("charts.faithGrounding")} k="faithGrounding" />
        </CardTitle>
        {onOpen ? <CardTabLink onOpen={onOpen} tab="signals" label={tq("seeDetail")} /> : null}
      </CardHeader>
      <CardContent>
        {loading && !pairs ? (
          <Skeleton className="h-32 w-full" />
        ) : points.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("charts.noData")}
          </p>
        ) : (
          <>
            <div className="relative h-16 w-full">
              <svg
                viewBox={`0 0 100 ${H + top * 2}`}
                preserveAspectRatio="none"
                className="h-full w-full"
                aria-hidden="true"
              >
                {[0, 0.5, 1].map((g) => (
                  <line
                    key={g}
                    x1={0}
                    x2={100}
                    y1={top + (1 - g) * H}
                    y2={top + (1 - g) * H}
                    stroke="var(--tessera-border)"
                    strokeWidth={0.3}
                  />
                ))}
                <line
                  x1={0}
                  y1={top + H}
                  x2={100}
                  y2={top}
                  stroke="var(--tessera-border)"
                  strokeDasharray="2 2"
                  strokeWidth={0.4}
                />
                {points.map((p, i) => (
                  <circle
                    key={`${p.x.toFixed(3)}:${p.y.toFixed(3)}:${i}`}
                    cx={p.x * 100}
                    cy={top + (1 - p.y) * H}
                    r={1.6}
                    fill={bucketColor((p.x + p.y) / 2)}
                  />
                ))}
              </svg>
            </div>
            <div className="mt-0.5 flex justify-between text-[0.6rem] text-[var(--muted-foreground)]">
              <span>↑ {tq("metrics.grounding")}</span>
              <span>{tq("metrics.faithfulness")} →</span>
            </div>
            <ul className="mt-1 flex flex-wrap gap-x-2 text-[0.6rem] text-[var(--muted-foreground)]">
              <li className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                {tq("charts.good")}
              </li>
              <li className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                {tq("charts.mid")}
              </li>
              <li className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                {tq("charts.low")}
              </li>
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** Identity per failure category — eight slots, exactly the ramp. */
const CAT_COLORS = [
  "var(--tessera-cat-1)",
  "var(--tessera-cat-2)",
  "var(--tessera-cat-3)",
  "var(--tessera-cat-4)",
  "var(--tessera-cat-5)",
  "var(--tessera-cat-6)",
  "var(--tessera-cat-7)",
  "var(--tessera-cat-8)",
];
const KNOWN_CATEGORIES = [
  "prompt_injection",
  "pii_leak",
  "hallucination",
  "overconfidence",
  "regulatory_misstatement",
  "citation_fabrication",
  "tool_misuse",
  "policy_violation",
  "language_mixing",
  "escalation_failure",
];
const SEV_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-amber-500",
  medium: "bg-blue-500",
  low: "bg-[var(--muted-foreground)]",
};
const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function useCatLabel() {
  const tq = useTranslations("quality");
  return (c: string) =>
    KNOWN_CATEGORIES.includes(c) ? tq(`failed.cat.${c}`) : c.replace(/_/g, " ");
}

/** "Répartition des échecs" as horizontal bars over the categories (zone B, image 00). */
export function FailureBars({
  report,
  loading,
  onOpen,
}: {
  report: FailedCasesReport | undefined;
  loading: boolean;
  onOpen?: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const catLabel = useCatLabel();
  const entries = Object.entries(report?.by_category ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <SubPanel
      title={tq("failed.distribution")}
      info={<KpiInfo title={tq("failed.distribution")} k="failureDistribution" />}
      action={
        onOpen ? <CardTabLink onOpen={onOpen} tab="failed" label={tq("seeDetail")} /> : undefined
      }
    >
      {loading && !report ? (
        <Skeleton className="h-32 w-full" />
      ) : entries.length === 0 ? (
        <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
          {tq("failed.empty")}
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5 text-[0.65rem]">
          {entries.map(([key, n], i) => (
            <li key={key} className="flex flex-col gap-0.5">
              <div className="flex items-start justify-between gap-1.5">
                <span className="min-w-0 leading-tight">{catLabel(key)}</span>
                <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{n}</span>
              </div>
              <div className="h-[4px] w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(4, (n / max) * 100)}%`,
                    background: CAT_COLORS[i % CAT_COLORS.length],
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </SubPanel>
  );
}

/** "Calibration du juge" — compact κ + agreement read for zone B (image 00). */
export function JudgeMini({
  data,
  loading,
  onOpen,
}: {
  data: Calibration | undefined;
  loading: boolean;
  onOpen?: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const kappa = data?.kappa ?? null;
  const tone = kappa == null ? MUTED : kappa >= 0.8 ? GOOD : kappa >= 0.6 ? WARN : BAD;
  return (
    <SubPanel
      title={tq("judge.title")}
      info={<KpiInfo title={tq("judge.title")} k="judgeCalibration" />}
      action={
        onOpen ? <CardTabLink onOpen={onOpen} tab="judge" label={tq("seeDetail")} /> : undefined
      }
    >
      {loading && !data ? (
        <Skeleton className="h-32 w-full" />
      ) : !data?.available ? (
        <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
          {tq("judge.unavailable")}
        </p>
      ) : (
        <div className="flex flex-col gap-1 text-[0.7rem]">
          <div className="flex items-baseline gap-1.5">
            <span className={`font-serif text-xl font-semibold tabular-nums ${tone}`}>
              {kappa == null ? "—" : kappa.toFixed(2)}
            </span>
            <span className="text-[var(--muted-foreground)]">{tq("judge.kappa")}</span>
          </div>
          <Row label={tq("judge.agreement")}>
            <span className="tabular-nums">{Math.round((data.agreement ?? 0) * 100)}%</span>
          </Row>
          <Row label={tq("judge.verbosity")}>
            <span className="tabular-nums">{(data.verbosity_corr ?? 0).toFixed(2)}</span>
          </Row>
          <Row label={tq("judge.samples")}>
            <span className="tabular-nums">{data.n ?? 0}</span>
          </Row>
        </div>
      )}
    </SubPanel>
  );
}

/** "Cas échoués prioritaires" — top failures by severity for zone B (image 00). */
export function PriorityCases({
  report,
  loading,
  onOpen,
}: {
  report: FailedCasesReport | undefined;
  loading: boolean;
  onOpen: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const cases = [...(report?.cases ?? [])]
    .sort(
      (a, b) =>
        (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) ||
        a.case_id.localeCompare(b.case_id),
    )
    .slice(0, 5);
  return (
    <SubPanel
      title={tq("exec.priorityCases")}
      info={<KpiInfo title={tq("exec.priorityCases")} k="priorityCases" />}
    >
      <div className="flex flex-col gap-1.5">
        {loading && !report ? (
          <Skeleton className="h-32 w-full" />
        ) : cases.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {tq("failed.empty")}
          </p>
        ) : (
          <>
            {cases.map((c) => (
              <div
                key={c.case_id}
                className="flex items-start gap-1.5 text-[0.65rem]"
                title={`${c.case_id} · ${c.title}`}
              >
                <span
                  className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${SEV_DOT[c.severity] ?? ""}`}
                />
                <span className="mt-px shrink-0 font-mono text-[0.6rem] text-[var(--tessera-green)]">
                  {shortCaseRef(c.case_id)}
                </span>
                <span className="line-clamp-2 min-w-0 flex-1 leading-snug">{c.title}</span>
              </div>
            ))}
            <button
              type="button"
              onClick={() => onOpen("failed")}
              className="mt-0.5 inline-flex items-center gap-1 self-start text-[0.65rem] text-[var(--tessera-green)] hover:underline"
            >
              {tq("rr.seeCases")}
              <ChevronRight className="h-3 w-3" />
            </button>
          </>
        )}
      </div>
    </SubPanel>
  );
}

/** One labelled mini bar (Intents/Langues à risque lists in zone C). */
function MiniBarRow({
  label,
  value,
  pct,
  color,
}: { label: string; value: string; pct: number; color: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center justify-between gap-2 text-[0.65rem]">
        <Truncate className="min-w-0">{label}</Truncate>
        <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{value}</span>
      </div>
      <div className="h-[4px] w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
        <div
          className="h-full rounded-full"
          style={{ width: `${Math.max(4, Math.min(100, pct))}%`, background: color }}
        />
      </div>
    </div>
  );
}

/** "C. Signaux prédictifs" — trend badge, regression-risk read, judge drift, the
 * failure predictor, and the at-risk intents/languages (all real, image 00). */
export function PredictiveSignals({
  series,
  risk,
  drift,
  predictor,
  intent,
  localization,
  loading,
}: {
  series: ScoreSeries | undefined;
  risk: RegressionRisk | undefined;
  drift: JudgeDrift | undefined;
  predictor: PredictorEvaluation | undefined;
  intent: IntentReport | undefined;
  localization: LocalizationReport | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const delta = series?.delta ?? null;
  const trend = delta == null ? "flat" : delta <= -0.02 ? "down" : delta >= 0.02 ? "up" : "flat";
  const trendTone = trend === "up" ? "success" : trend === "down" ? "warning" : "neutral";

  const prob = risk?.probability_7d ?? null;
  const riskScore = risk?.risk_score ?? null;
  const riskTone =
    riskScore == null ? MUTED : riskScore >= 0.5 ? BAD : riskScore >= 0.25 ? WARN : GOOD;
  const div = drift?.divergence ?? null;
  const driftLevel = drift?.level ?? "unknown";

  const intents = intent
    ? Object.entries(intent.distribution)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
    : [];
  const intentMax = Math.max(1, ...intents.map(([, n]) => n));
  const langs = (localization?.locales ?? [])
    .map((l) => ({ locale: l.locale, gap: 1 - l.completeness }))
    .sort((a, b) => b.gap - a.gap)
    .slice(0, 3);
  const langMax = Math.max(0.01, ...langs.map((l) => l.gap));

  return (
    <Card>
      <CardContent className="flex flex-col gap-2 pt-3 text-xs">
        {loading && !risk ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <>
            <Row label={tq("pred.trend")}>
              <Badge tone={trendTone}>{tq(`pred.trend_${trend}`)}</Badge>
            </Row>
            <div className="flex flex-col gap-1.5 border-t border-[var(--tessera-border)] pt-1.5">
              <Row label={tq("pred.prob7")}>
                <span className="tabular-nums">
                  {prob == null ? "—" : `${Math.round(prob * 100)}%`}
                </span>
              </Row>
              <Row label={tq("pred.risk")}>
                <span className={`tabular-nums ${riskTone}`}>
                  {riskScore == null ? "—" : `${riskScore.toFixed(2)}/1`}
                </span>
              </Row>
              <Row label={tq("pred.drift")}>
                <span className="flex items-center gap-1.5">
                  <span className="tabular-nums">
                    {div == null ? "—" : `${(div * 100).toFixed(1)}%`}
                  </span>
                  <Badge
                    tone={
                      driftLevel === "stable" || driftLevel === "low"
                        ? "success"
                        : driftLevel === "unknown"
                          ? "neutral"
                          : "warning"
                    }
                  >
                    {tq(`judge.drift_${driftLevel}`)}
                  </Badge>
                </span>
              </Row>
              <Row label={tq("pred.predictor")}>
                {predictor && predictor.n > 0 ? (
                  <span className="tabular-nums">
                    {Math.round(predictor.precision * 100)}% · {predictor.n}
                  </span>
                ) : (
                  <span className={MUTED}>{tq("pred.predictorUntrained")}</span>
                )}
              </Row>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 border-t border-[var(--tessera-border)] pt-1.5">
              <div className="flex flex-col gap-1">
                <span className="text-[0.65rem] font-medium text-[var(--muted-foreground)]">
                  {tq("pred.intents")}
                </span>
                {intents.length === 0 ? (
                  <span className="text-xs text-[var(--muted-foreground)]">—</span>
                ) : (
                  intents.map(([name, n], i) => (
                    <MiniBarRow
                      key={name}
                      label={name}
                      value={String(n)}
                      pct={(n / intentMax) * 100}
                      color={CAT_COLORS[i % CAT_COLORS.length] ?? "var(--tessera-text-muted)"}
                    />
                  ))
                )}
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-[0.65rem] font-medium text-[var(--muted-foreground)]">
                  {tq("pred.langs")}
                </span>
                {langs.length === 0 ? (
                  <span className="text-xs text-[var(--muted-foreground)]">—</span>
                ) : (
                  langs.map((l, i) => (
                    <MiniBarRow
                      key={l.locale}
                      label={l.locale.toUpperCase()}
                      value={`${Math.round(l.gap * 100)}%`}
                      pct={(l.gap / langMax) * 100}
                      color={CAT_COLORS[(i + 3) % CAT_COLORS.length] ?? "var(--tessera-text-muted)"}
                    />
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

/** "Pass-rate des derniers runs" — compact table for the charts row (image 00). */
export function RunsPassRateTable({
  registry,
  loading,
}: {
  registry: RunRegistry | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const runs = [...(registry?.runs ?? [])]
    .sort((a, b) => b.run_at.localeCompare(a.run_at))
    .slice(0, 4);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("charts.runsBars")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !registry ? (
          <Skeleton className="h-40 w-full" />
        ) : runs.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("runs.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                  <th className="py-1 pr-3 font-medium">{tq("runs.cols.model")}</th>
                  <th className="py-1 pr-3 font-medium">{tq("charts.dataset")}</th>
                  <th className="py-1 pr-3 font-medium">{tq("runs.cols.rate")}</th>
                  <th className="py-1 font-medium">{tq("charts.passTotal")}</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-b border-[var(--border)]/50">
                    <td className="py-1 pr-3 font-medium whitespace-nowrap">{r.model}</td>
                    <td className="py-1 pr-3 font-mono text-[var(--muted-foreground)] whitespace-nowrap">
                      regression-{r.language}
                    </td>
                    <td
                      className={`py-1 pr-3 font-semibold tabular-nums ${r.pass_rate >= 0.8 ? GOOD : r.pass_rate >= 0.5 ? WARN : BAD}`}
                    >
                      {Math.round(r.pass_rate * 100)}%
                    </td>
                    <td className="py-1 tabular-nums text-[var(--muted-foreground)]">
                      {r.passed}/{r.total}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** "Régressions par release" — open run-over-run regressions as bars (image 00). */
export function RegressionsByRelease({
  release,
  loading,
}: {
  release: ReleaseStatus | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const regs = release?.regressions ?? [];
  const max = Math.max(0.01, ...regs.map((r) => Math.abs(r.delta)));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("charts.regressionsByRelease")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !release ? (
          <Skeleton className="h-40 w-full" />
        ) : regs.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("charts.noRegressions")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2.5 text-xs">
            {regs.map((r) => (
              <li key={r.model} className="flex flex-col gap-1">
                <div className="flex items-center justify-between gap-2">
                  <Truncate className="font-medium">{r.model}</Truncate>
                  <span className="shrink-0 tabular-nums text-[var(--tessera-fg-danger)]">
                    {Math.round(r.delta * 100)} pts
                  </span>
                </div>
                <div className="h-[4px] w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
                  <div
                    className="h-full rounded-full bg-red-500"
                    style={{ width: `${Math.max(4, (Math.abs(r.delta) / max) * 100)}%` }}
                  />
                </div>
                <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                  {Math.round(r.prev_rate * 100)}% → {Math.round(r.last_rate * 100)}%
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

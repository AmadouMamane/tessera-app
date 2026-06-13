"use client";

import {
  BookCheck,
  ChevronRight,
  Database,
  ListChecks,
  ListPlus,
  Lock,
  RefreshCw,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricKpi } from "@/components/observability/evolution-chart";
import type { SignalRow } from "@/components/observability/signals-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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

/** A plain value KPI tile (no time series), with an optional tone + hint. */
function ValueKpi({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: string;
  hint?: string;
}) {
  return (
    <Card className="flex flex-col gap-1 p-3">
      <div className="truncate text-xs text-[var(--muted-foreground)]">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
      </div>
      {hint ? <div className="text-[0.65rem] text-[var(--muted-foreground)]">{hint}</div> : null}
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
        stroke={rising ? "#10b981" : "#ef4444"}
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
  failedCount,
  loading,
}: {
  sloPct: number | null;
  faithfulness: ScoreSeries | undefined;
  grounding: ScoreSeries | undefined;
  hallucination: ScoreSeries | undefined;
  nonRegression: number | null;
  nRegressions: number | null;
  kappa: number | null;
  failedCount: number | null;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const scoreTone = sloPct == null ? MUTED : sloPct >= 80 ? GOOD : sloPct >= 60 ? WARN : BAD;
  const nonRegTone =
    nonRegression == null ? MUTED : nonRegression >= 0.9 ? GOOD : nonRegression >= 0.7 ? WARN : BAD;
  const regTone = nRegressions == null ? MUTED : nRegressions === 0 ? GOOD : WARN;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 2xl:grid-cols-8">
      <ValueKpi
        label={tq("exec.kpi.scoreGlobal")}
        value={sloPct == null ? "—" : `${sloPct}`}
        tone={scoreTone}
        hint="/100"
      />
      <MetricKpi label={tq("metrics.faithfulness")} series={faithfulness} loading={loading} />
      <MetricKpi label={tq("metrics.grounding")} series={grounding} loading={loading} />
      <ValueKpi
        label={tq("exec.kpi.nonRegression")}
        value={nonRegression == null ? "—" : `${Math.round(nonRegression * 100)}%`}
        tone={nonRegTone}
      />
      <MetricKpi label={tq("metrics.hallucination")} series={hallucination} loading={loading} />
      <ValueKpi
        label={tq("exec.kpi.regressionsOpen")}
        value={nRegressions == null ? "—" : String(nRegressions)}
        tone={regTone}
      />
      <ValueKpi label={tq("exec.kpi.judgeKappa")} value={kappa == null ? "—" : kappa.toFixed(2)} />
      <ValueKpi
        label={tq("exec.kpi.casFailed")}
        value={failedCount == null ? "—" : String(failedCount)}
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
      <CardHeader>
        <CardTitle className="text-sm">{tq("sec.etat")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <Row label={tq("exec.etat.globalQuality")}>
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
        <div className="flex items-center justify-between gap-2 border-t border-[var(--tessera-border)] pt-2">
          <span className="text-[var(--muted-foreground)]">{tq("exec.etat.releaseLabel")}</span>
          {current ? (
            <span className="flex items-center gap-1.5">
              <span className="font-mono text-xs tabular-nums">{current.version}</span>
              <Badge tone={blocked ? "danger" : "success"}>
                {blocked ? tq("rr.blocked") : tq("rr.inProd")}
              </Badge>
            </span>
          ) : (
            <span className={MUTED}>—</span>
          )}
        </div>
        <div className="flex flex-col gap-1 border-t border-[var(--tessera-border)] pt-2">
          <span className="text-[var(--muted-foreground)]">{tq("exec.etat.evolutionVsPrev")}</span>
          <div className="flex items-center justify-between gap-2">
            <span className={`text-lg font-semibold tabular-nums ${evoTone}`}>
              {evoPts == null ? "—" : `${evoPts >= 0 ? "+" : ""}${evoPts} pts`}
            </span>
            <MiniSpark series={series} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{label}</span>
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
  best: "#10b981",
  balanced: "#3b82f6",
  economic: "#10b981",
  avoid: "#ef4444",
};

function rateColor(r: number): string {
  return r >= 0.8 ? "#10b981" : r >= 0.5 ? "#f59e0b" : "#ef4444";
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
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("charts.diagnostic")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {tq("charts.noDiag")}
          </p>
        </CardContent>
      </Card>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("charts.diagnostic")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        <section>
          <h4 className="mb-1 text-xs font-semibold text-[var(--muted-foreground)]">
            {tq("charts.whatChangedTitle")}
          </h4>
          <ul className="flex flex-col gap-1">
            {changes.map((c) => (
              <li key={c.field} className="font-mono text-xs">
                {c.field}: {c.before.slice(0, 8)} → {c.after.slice(0, 8)}
              </li>
            ))}
            {docsAdded.length ? (
              <li className="text-xs text-emerald-500">+{docsAdded.length} docs</li>
            ) : null}
            {docsRemoved.length ? (
              <li className="text-xs text-red-500">−{docsRemoved.length} docs</li>
            ) : null}
          </ul>
        </section>
        <section>
          <h4 className="mb-1 text-xs font-semibold text-[var(--muted-foreground)]">
            {tq("charts.causes")}
          </h4>
          <ul className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
            {causes.map((c) => (
              <li key={c}>• {c}</li>
            ))}
          </ul>
        </section>
        <section>
          <h4 className="mb-1 text-xs font-semibold text-[var(--muted-foreground)]">
            {tq("charts.impact")}
          </h4>
          <div className="flex flex-wrap items-center gap-2">
            {delta != null ? (
              <Badge tone={delta >= 0 ? "success" : "danger"} className="tabular-nums">
                {delta >= 0 ? "+" : ""}
                {Math.round(delta * 100)} pts
              </Badge>
            ) : null}
            {regressions.map((r) => (
              <span key={r.model} className="text-xs text-red-500">
                {r.model} {Math.round(r.prev_rate * 100)}→{Math.round(r.last_rate * 100)}%
              </span>
            ))}
          </div>
        </section>
      </CardContent>
    </Card>
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
      <CardHeader>
        <CardTitle className="text-sm">{tq("sec.actions")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {actions.map((a) => (
          <button
            key={a.key}
            type="button"
            onClick={() => onOpen(a.target)}
            className="group flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2.5 py-1.5 text-left text-sm transition-colors hover:border-[var(--tessera-border-strong)] hover:bg-[var(--tessera-muted)]"
          >
            <a.icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
            <span className="min-w-0 flex-1 truncate">{a.label}</span>
            {a.ctx ? (
              <span className="shrink-0 truncate text-[0.7rem] text-[var(--muted-foreground)]">
                {a.ctx}
              </span>
            ) : null}
            <Badge tone={a.role === "admin" ? "warning" : "success"}>
              {a.role === "admin" ? "Admin+" : "Operator+"}
            </Badge>
          </button>
        ))}
        <button
          type="button"
          onClick={onEvidence}
          className="mt-1 inline-flex items-center gap-1 self-start text-xs text-[var(--tessera-green)] hover:underline"
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
            <div className="relative h-32 w-full">
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
                    fill={VERDICT_COLOR[m.verdict] ?? "#64748b"}
                  />
                ))}
              </svg>
            </div>
            <div className="mt-1 flex justify-between text-[0.65rem] text-[var(--muted-foreground)]">
              <span>↑ {tq("charts.qualityAxis")}</span>
              <span>{tq("charts.costAxis")} →</span>
            </div>
            <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs">
              {models.map((m) => (
                <li
                  key={m.model}
                  className="flex items-center gap-1 text-[var(--muted-foreground)]"
                >
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: VERDICT_COLOR[m.verdict] ?? "#64748b" }}
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
}: {
  pairs: MetricPairs | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const points = pairs?.points ?? [];
  const H = 56;
  const top = 4;
  const bucketColor = (m: number) => (m >= 0.7 ? "#10b981" : m >= 0.4 ? "#f59e0b" : "#ef4444");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("charts.faithGrounding")}</CardTitle>
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
            <div className="relative h-32 w-full">
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
            <div className="mt-1 flex justify-between text-[0.65rem] text-[var(--muted-foreground)]">
              <span>↑ {tq("metrics.grounding")}</span>
              <span>{tq("metrics.faithfulness")} →</span>
            </div>
            <ul className="mt-2 flex flex-wrap gap-x-3 text-xs text-[var(--muted-foreground)]">
              <li className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                {tq("charts.good")}
              </li>
              <li className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                {tq("charts.mid")}
              </li>
              <li className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-500" />
                {tq("charts.low")}
              </li>
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

const CAT_COLORS = [
  "#ef4444",
  "#f59e0b",
  "#3b82f6",
  "#8b5cf6",
  "#10b981",
  "#ec4899",
  "#14b8a6",
  "#f97316",
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
}: {
  report: FailedCasesReport | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const catLabel = useCatLabel();
  const entries = Object.entries(report?.by_category ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("failed.distribution")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !report ? (
          <Skeleton className="h-32 w-full" />
        ) : entries.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {tq("failed.empty")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2 text-xs">
            {entries.map(([key, n], i) => (
              <li key={key} className="flex flex-col gap-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate">{catLabel(key)}</span>
                  <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{n}</span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
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
      </CardContent>
    </Card>
  );
}

/** "Calibration du juge" — compact κ + agreement read for zone B (image 00). */
export function JudgeMini({ data, loading }: { data: Calibration | undefined; loading: boolean }) {
  const tq = useTranslations("quality");
  const kappa = data?.kappa ?? null;
  const tone = kappa == null ? MUTED : kappa >= 0.8 ? GOOD : kappa >= 0.6 ? WARN : BAD;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("judge.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !data ? (
          <Skeleton className="h-32 w-full" />
        ) : !data?.available ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {tq("judge.unavailable")}
          </p>
        ) : (
          <div className="flex flex-col gap-2 text-xs">
            <div className="flex items-baseline gap-1.5">
              <span className={`font-serif text-2xl font-semibold tabular-nums ${tone}`}>
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
      </CardContent>
    </Card>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("exec.priorityCases")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {loading && !report ? (
          <Skeleton className="h-32 w-full" />
        ) : cases.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {tq("failed.empty")}
          </p>
        ) : (
          <>
            {cases.map((c) => (
              <div key={c.case_id} className="flex items-center gap-2 text-xs">
                <span className={`h-2 w-2 shrink-0 rounded-full ${SEV_DOT[c.severity] ?? ""}`} />
                <span className="shrink-0 font-mono text-[var(--muted-foreground)]">
                  {c.case_id}
                </span>
                <span className="min-w-0 flex-1 truncate">{c.title}</span>
              </div>
            ))}
            <button
              type="button"
              onClick={() => onOpen("failed")}
              className="mt-1 inline-flex items-center gap-1 self-start text-xs text-[var(--tessera-green)] hover:underline"
            >
              {tq("rr.seeCases")}
              <ChevronRight className="h-3 w-3" />
            </button>
          </>
        )}
      </CardContent>
    </Card>
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
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="min-w-0 truncate">{label}</span>
        <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{value}</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
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
      <CardHeader>
        <CardTitle className="text-sm">{tq("sec.predictive")}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm">
        {loading && !risk ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <>
            <Row label={tq("pred.trend")}>
              <Badge tone={trendTone}>{tq(`pred.trend_${trend}`)}</Badge>
            </Row>
            <div className="flex flex-col gap-2 border-t border-[var(--tessera-border)] pt-2 text-xs">
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
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 border-t border-[var(--tessera-border)] pt-2">
              <div className="flex flex-col gap-1.5">
                <span className="text-[0.7rem] font-medium text-[var(--muted-foreground)]">
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
                      color={CAT_COLORS[i % CAT_COLORS.length] ?? "#64748b"}
                    />
                  ))
                )}
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="text-[0.7rem] font-medium text-[var(--muted-foreground)]">
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
                      color={CAT_COLORS[(i + 3) % CAT_COLORS.length] ?? "#64748b"}
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
    .slice(0, 5);
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
                  <th className="py-1.5 pr-3 font-medium">{tq("runs.cols.model")}</th>
                  <th className="py-1.5 pr-3 font-medium">{tq("charts.dataset")}</th>
                  <th className="py-1.5 pr-3 font-medium">{tq("runs.cols.rate")}</th>
                  <th className="py-1.5 font-medium">{tq("charts.passTotal")}</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="border-b border-[var(--border)]/50">
                    <td className="py-1.5 pr-3 font-medium whitespace-nowrap">{r.model}</td>
                    <td className="py-1.5 pr-3 font-mono text-[var(--muted-foreground)] whitespace-nowrap">
                      regression-{r.language}
                    </td>
                    <td
                      className={`py-1.5 pr-3 font-semibold tabular-nums ${r.pass_rate >= 0.8 ? GOOD : r.pass_rate >= 0.5 ? WARN : BAD}`}
                    >
                      {Math.round(r.pass_rate * 100)}%
                    </td>
                    <td className="py-1.5 tabular-nums text-[var(--muted-foreground)]">
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
                  <span className="truncate font-medium">{r.model}</span>
                  <span className="shrink-0 tabular-nums text-red-500">
                    {Math.round(r.delta * 100)} pts
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
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

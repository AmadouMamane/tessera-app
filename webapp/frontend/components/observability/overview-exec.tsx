"use client";

import { BookCheck, ChevronRight, Lock, Receipt, Repeat, Scissors } from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricKpi } from "@/components/observability/evolution-chart";
import type { SignalRow } from "@/components/observability/signals-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  FailedCasesReport,
  MetricPairs,
  ModelComparison,
  Regression,
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

/** The 8-tile headline KPI strip of the Vue d'ensemble (reference image 00). */
export function OverviewKpis({
  sloPct,
  faithfulness,
  grounding,
  hallucination,
  nonRegression,
  nRegressions,
  kappa,
  casEvalues,
  loading,
}: {
  sloPct: number | null;
  faithfulness: ScoreSeries | undefined;
  grounding: ScoreSeries | undefined;
  hallucination: ScoreSeries | undefined;
  nonRegression: number | null;
  nRegressions: number | null;
  kappa: number | null;
  casEvalues: number | null;
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
      <MetricKpi label={tq("metrics.hallucination")} series={hallucination} loading={loading} />
      <ValueKpi
        label={tq("exec.kpi.nonRegression")}
        value={nonRegression == null ? "—" : `${Math.round(nonRegression * 100)}%`}
        tone={nonRegTone}
      />
      <ValueKpi
        label={tq("exec.kpi.regressionsOpen")}
        value={nRegressions == null ? "—" : String(nRegressions)}
        tone={regTone}
      />
      <ValueKpi label={tq("exec.kpi.judgeKappa")} value={kappa == null ? "—" : kappa.toFixed(2)} />
      <ValueKpi
        label={tq("exec.kpi.casEval")}
        value={casEvalues == null ? "—" : String(casEvalues)}
      />
    </div>
  );
}

/** Compact single-arc score donut shown inside État actuel (image 00). */
function ScoreDonut({ scorePct, dir }: { scorePct: number | null; dir: string }) {
  const tq = useTranslations("quality");
  const r = 46;
  const circ = 2 * Math.PI * r;
  const pct = scorePct == null ? 0 : Math.max(0, Math.min(100, scorePct));
  const arc = (pct / 100) * circ;
  const color =
    scorePct == null ? "#64748b" : pct >= 80 ? "#10b981" : pct >= 60 ? "#f59e0b" : "#ef4444";
  const dirTone = dir === "rising" ? GOOD : dir === "falling" ? BAD : MUTED;
  return (
    <div className="relative h-[128px] w-[128px] shrink-0">
      <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="64" cy="64" r={r} fill="none" stroke="var(--tessera-border)" strokeWidth="11" />
        <circle
          cx="64"
          cy="64"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${arc} ${circ - arc}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-serif text-3xl font-semibold tabular-nums" style={{ color }}>
          {scorePct == null ? "—" : scorePct}
        </span>
        <span className="text-[0.65rem] text-[var(--muted-foreground)]">/ 100</span>
        <span className={`mt-0.5 text-[0.65rem] ${dirTone}`}>
          {dir === "rising" ? "↑" : dir === "falling" ? "↓" : "→"} {tq(`exec.etat.${dir}`)}
        </span>
      </div>
    </div>
  );
}

/** "État actuel" — failing/alert counts, release impact, evolution + score donut (image 00). */
export function EtatActuel({
  summary,
  release,
  evolutionDelta,
  scorePct,
}: {
  summary: { ok: number; warn: number; crit: number; na: number; total: number };
  release: ReleaseStatus | undefined;
  evolutionDelta: number | null;
  scorePct: number | null;
}) {
  const tq = useTranslations("quality");
  const nReg = release?.n_regressions ?? null;
  const impact = nReg == null ? null : nReg === 0 ? "low" : nReg <= 2 ? "medium" : "high";
  const evoPts = evolutionDelta == null ? null : Math.round(evolutionDelta * 100);
  const evoDir = evoPts == null ? "flat" : evoPts > 0 ? "rising" : evoPts < 0 ? "falling" : "flat";
  const evoTone = evoDir === "rising" ? GOOD : evoDir === "falling" ? BAD : MUTED;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("exec.etat.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center gap-4 text-sm">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <Row label={tq("exec.etat.failing")}>
            <span className={summary.crit > 0 ? BAD : MUTED}>
              {summary.crit} {tq("signalsTable.status.crit").toLowerCase()}
            </span>
          </Row>
          <Row label={tq("exec.etat.alert")}>
            <span className={summary.warn > 0 ? WARN : MUTED}>
              {summary.warn} {tq("signalsTable.status.warn").toLowerCase()}
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
          <Row label={tq("exec.etat.evolution")}>
            <span className={`tabular-nums ${evoTone}`}>
              {evoPts == null ? "—" : `${evoPts >= 0 ? "+" : ""}${evoPts} pts`}
            </span>
          </Row>
        </div>
        <ScoreDonut scorePct={scorePct} dir={evoDir} />
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

/** "D. Actions recommandées" — governed actions derived from the live signals,
 * each carrying the required role and a link into the relevant tab (image 00). */
export function RecommendedActions({
  regressions,
  topFailing,
  failed,
  onOpen,
}: {
  regressions: Regression[];
  topFailing: { dominant_category: string; size: number }[];
  failed: FailedCasesReport | undefined;
  onOpen: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const top = topFailing[0];
  const failedTotal = failed?.n ?? null;
  const actions: {
    key: string;
    icon: typeof Scissors;
    label: string;
    role: "operator" | "admin";
    ctx: string | null;
    target: OverviewTab;
  }[] = [
    {
      key: "curate",
      icon: Scissors,
      label: tq("reco.curate"),
      role: "operator",
      ctx: failedTotal != null ? `${failedTotal}` : null,
      target: "failed",
    },
    {
      key: "freeze",
      icon: Lock,
      label: tq("reco.freeze"),
      role: "admin",
      ctx: regressions.length > 0 ? `${regressions.length}` : null,
      target: "models",
    },
    {
      key: "playbook",
      icon: BookCheck,
      label: tq("reco.playbook"),
      role: "operator",
      ctx: top ? top.dominant_category : null,
      target: "failed",
    },
    {
      key: "shadow",
      icon: Repeat,
      label: tq("reco.shadow"),
      role: "operator",
      ctx: null,
      target: "runs",
    },
    {
      key: "ticket",
      icon: Receipt,
      label: tq("reco.ticket"),
      role: "admin",
      ctx: null,
      target: "failed",
    },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("reco.title")}</CardTitle>
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
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)] opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        ))}
        <p className="mt-1 text-[0.7rem] text-[var(--muted-foreground)]">{tq("reco.caption")}</p>
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
          <Skeleton className="h-44 w-full" />
        ) : (
          <>
            <div className="relative h-44 w-full">
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
          <Skeleton className="h-44 w-full" />
        ) : points.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("charts.noData")}
          </p>
        ) : (
          <>
            <div className="relative h-44 w-full">
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

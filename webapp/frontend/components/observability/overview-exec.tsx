"use client";

import { useTranslations } from "next-intl";

import { MetricKpi } from "@/components/observability/evolution-chart";
import type { SignalRow } from "@/components/observability/signals-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ReleaseStatus, ScoreSeries } from "@/lib/api/schemas";

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

/** "État actuel" — failing/alert counts, release impact, period evolution (image 00). */
export function EtatActuel({
  summary,
  release,
  evolutionDelta,
}: {
  summary: { ok: number; warn: number; crit: number; na: number; total: number };
  release: ReleaseStatus | undefined;
  evolutionDelta: number | null;
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
      <CardContent className="flex flex-col gap-3 text-sm">
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
            {evoPts == null ? "—" : `${evoPts >= 0 ? "+" : ""}${evoPts} pts`} ·{" "}
            {tq(`exec.etat.${evoDir}`)}
          </span>
        </Row>
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

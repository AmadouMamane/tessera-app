"use client";

import { Award, Coins, Crosshair, Gauge, ShieldAlert, Sparkles, Target } from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Calibration, ModelComparison, ModelStat, ReleaseStatus } from "@/lib/api/schemas";

const DASH = "—";

const VERDICT_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  best: "success",
  balanced: "neutral",
  economic: "neutral",
  avoid: "danger",
};

function shortModel(m: string): string {
  return m.split(":")[0] ?? m;
}

function pctOrDash(v: number | null | undefined): string {
  return v == null ? DASH : `${Math.round(v * 100)}%`;
}

function scoreBand(rate: number): string {
  if (rate >= 0.8) return "#34d399";
  if (rate >= 0.5) return "#f59e0b";
  return "#f87171";
}

function scoreToneClass(rate: number): string {
  if (rate >= 0.8) return "text-emerald-500";
  if (rate >= 0.5) return "text-amber-500";
  return "text-red-500";
}

function fmtScore(rate: number): string {
  return String(Math.round(rate * 100));
}

function fmtCost(eur: number | null | undefined): string {
  if (eur == null) return DASH;
  if (eur === 0) return "0 €";
  return `${eur.toFixed(2).replace(".", ",")} €`;
}

// ──────────────────────────────── KPI strip ──────────────────────────────────

function Kpi({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: React.ReactNode;
  tone?: string;
}) {
  return (
    <Card className="flex flex-col gap-0.5 p-2.5">
      <span className="flex items-center gap-1 text-[0.65rem] text-[var(--muted-foreground)]">
        <span className="opacity-70">{icon}</span>
        {label}
      </span>
      <span className={`text-xl font-semibold leading-tight tabular-nums ${tone ?? ""}`}>
        {value}
      </span>
      {sub ? <span className="text-[0.6rem] text-[var(--muted-foreground)]">{sub}</span> : null}
    </Card>
  );
}

/** Delta vs the previous run, from the referent model's evolution sparkline. */
function evoDelta(evo: number[] | undefined): number | null {
  if (!evo || evo.length < 2) return null;
  const last = evo[evo.length - 1];
  const prev = evo[evo.length - 2];
  if (last == null || prev == null) return null;
  return last - prev;
}

function DeltaSub({ delta, unit = "pts" }: { delta: number | null; unit?: string }) {
  const tq = useTranslations("quality");
  if (delta == null) return <>{tq("models.kpi.vsPrev", { d: DASH })}</>;
  const pts = Math.round(delta * 100);
  const tone = pts > 0 ? "text-emerald-500" : pts < 0 ? "text-red-500" : "";
  return (
    <span className={tone}>
      {pts > 0 ? "+" : ""}
      {pts} {unit}
    </span>
  );
}

function ModelsKpis({
  comparison,
  calibration,
}: {
  comparison: ModelComparison | undefined;
  calibration: Calibration | undefined;
}) {
  const tq = useTranslations("quality");
  const models = comparison?.models ?? [];
  const ref = models[0]; // compare_models sorts best pass-rate first
  const kappa = calibration?.kappa;
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
      <Kpi
        icon={<Award className="h-3.5 w-3.5" />}
        label={tq("models.kpi.referent")}
        value={ref ? shortModel(ref.model) : DASH}
        sub={
          ref ? (
            <Badge tone="success" className="text-[0.55rem]">
              {tq("models.kpi.referentBadge")}
            </Badge>
          ) : undefined
        }
      />
      <Kpi
        icon={<Gauge className="h-3.5 w-3.5" />}
        label={tq("models.kpi.score")}
        value={ref ? `${fmtScore(ref.pass_rate)}/100` : DASH}
        tone={ref ? scoreToneClass(ref.pass_rate) : undefined}
        sub={<DeltaSub delta={evoDelta(ref?.evolution)} />}
      />
      <Kpi
        icon={<Target className="h-3.5 w-3.5" />}
        label={tq("models.kpi.faithfulness")}
        value={ref?.faithfulness != null ? ref.faithfulness.toFixed(2) : DASH}
      />
      <Kpi
        icon={<Crosshair className="h-3.5 w-3.5" />}
        label={tq("models.kpi.grounding")}
        value={pctOrDash(ref?.grounding)}
      />
      <Kpi
        icon={<ShieldAlert className="h-3.5 w-3.5" />}
        label={tq("models.kpi.hallucination")}
        value={ref?.hallucination != null ? `${Math.round((1 - ref.hallucination) * 100)}%` : DASH}
        tone="text-amber-500"
      />
      <Kpi
        icon={<Sparkles className="h-3.5 w-3.5" />}
        label={tq("models.kpi.kappa")}
        value={kappa != null ? kappa.toFixed(2) : DASH}
        sub={tq("models.kpi.kappaGlobal")}
      />
      <Kpi
        icon={<Coins className="h-3.5 w-3.5" />}
        label={tq("models.kpi.cases")}
        value={ref ? String(ref.total_cases) : DASH}
        sub={tq("models.kpi.active", { n: models.length })}
      />
    </div>
  );
}

// ──────────────────────────────── sparkline ──────────────────────────────────

function Spark({ values }: { values: number[] | undefined }) {
  if (!values || values.length < 2)
    return <span className="text-[var(--muted-foreground)]">{DASH}</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 56;
  const h = 16;
  const pts = values
    .map(
      (v, i) =>
        `${((i / (values.length - 1)) * w).toFixed(1)},${(h - 2 - ((v - min) / span) * (h - 4)).toFixed(1)}`,
    )
    .join(" ");
  const up = (values[values.length - 1] ?? 0) >= (values[0] ?? 0);
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="h-4 w-14"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <polyline points={pts} fill="none" stroke={up ? "#34d399" : "#f87171"} strokeWidth={1.5} />
    </svg>
  );
}

// ──────────────────────────── detailed comparison ────────────────────────────

function ModelsTable({ comparison }: { comparison: ModelComparison | undefined }) {
  const tq = useTranslations("quality");
  const models = comparison?.models ?? [];
  const verdictLabel = (v: string) =>
    ["best", "balanced", "economic", "avoid"].includes(v) ? tq(`models.verdict.${v}`) : v;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between pb-1">
        <CardTitle className="text-sm">{tq("models.table.title")}</CardTitle>
        {comparison?.judge_model ? (
          <Badge tone="neutral" className="text-[0.6rem]">
            {tq("models.table.judge", { m: comparison.judge_model })}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="overflow-x-auto">
        {models.length === 0 ? (
          <p className="py-6 text-center text-xs text-[var(--muted-foreground)]">
            {tq("models.empty")}
          </p>
        ) : (
          <table className="w-full text-left text-[0.7rem]">
            <thead className="text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
              <tr className="border-b border-[var(--border)]">
                <th className="py-1.5 pr-2 font-medium">{tq("models.cols.model")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.score")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.faith")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">
                  {tq("models.cols.grounding")}
                </th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.nonReg")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.hallu")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.kappa")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.cases")}</th>
                <th className="py-1.5 pr-2 text-right font-medium">{tq("models.cols.cost")}</th>
                <th className="py-1.5 pr-2 font-medium">{tq("models.cols.evolution")}</th>
                <th className="py-1.5 pr-2 font-medium">{tq("models.cols.verdict")}</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m, i) => (
                <tr key={m.model} className="border-b border-[var(--border)]/50">
                  <td className="py-1.5 pr-2 font-medium text-[var(--foreground)]">
                    <span className="flex items-center gap-1.5">
                      {shortModel(m.model)}
                      {i === 0 ? (
                        <Badge tone="success" className="text-[0.5rem]">
                          {tq("models.kpi.referentBadge")}
                        </Badge>
                      ) : null}
                    </span>
                  </td>
                  <td className="py-1.5 pr-2 text-right font-semibold tabular-nums">
                    <span style={{ color: scoreBand(m.pass_rate) }}>{fmtScore(m.pass_rate)}</span>
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">
                    {m.faithfulness != null ? m.faithfulness.toFixed(2) : DASH}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{pctOrDash(m.grounding)}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">
                    {pctOrDash(m.non_regression)}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-amber-600 dark:text-amber-400">
                    {m.hallucination != null ? `${Math.round((1 - m.hallucination) * 100)}%` : DASH}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-[var(--muted-foreground)]">
                    {DASH}
                  </td>
                  <td className="py-1.5 pr-2 text-right tabular-nums">{m.total_cases}</td>
                  <td className="py-1.5 pr-2 text-right tabular-nums text-[var(--muted-foreground)]">
                    {fmtCost(m.est_cost_eur)}
                  </td>
                  <td className="py-1.5 pr-2">
                    <Spark values={m.evolution} />
                  </td>
                  <td className="py-1.5 pr-2">
                    <Badge tone={VERDICT_TONE[m.verdict] ?? "neutral"} className="text-[0.6rem]">
                      {verdictLabel(m.verdict)}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}

// ──────────────────────────────── scatters ───────────────────────────────────

const POINT_COLORS = ["#34d399", "#60a5fa", "#f59e0b", "#a78bfa", "#f87171", "#22d3ee"];

/** Generic per-model scatter with axis-normalised points and a legend. */
function ModelScatter({
  models,
  x,
  y,
  xLabel,
  yLabel,
}: {
  models: ModelStat[];
  x: (m: ModelStat) => number | null | undefined;
  y: (m: ModelStat) => number | null | undefined;
  xLabel: string;
  yLabel: string;
}) {
  const tq = useTranslations("quality");
  const pts = models
    .map((m, i) => ({ m, i, xv: x(m), yv: y(m) }))
    .filter(
      (p): p is { m: ModelStat; i: number; xv: number; yv: number } => p.xv != null && p.yv != null,
    );
  if (pts.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  const xs = pts.map((p) => p.xv);
  const ys = pts.map((p) => p.yv);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const w = 200;
  const h = 96;
  const px = (v: number) => 6 + ((v - xMin) / (xMax - xMin || 1)) * (w - 12);
  const py = (v: number) => h - 14 - ((v - yMin) / (yMax - yMin || 1)) * (h - 22);
  return (
    <div className="flex flex-col gap-1">
      <svg viewBox={`0 0 ${w} ${h}`} className="h-24 w-full" aria-hidden="true">
        {pts.map((p) => (
          <circle
            key={p.m.model}
            cx={px(p.xv)}
            cy={py(p.yv)}
            r={3}
            fill={POINT_COLORS[p.i % POINT_COLORS.length]}
          />
        ))}
        <text
          x={w / 2}
          y={h - 2}
          textAnchor="middle"
          className="fill-[var(--muted-foreground)] text-[6px]"
        >
          {xLabel}
        </text>
        <text x={3} y={8} className="fill-[var(--muted-foreground)] text-[6px]">
          {yLabel}
        </text>
      </svg>
      <ul className="flex flex-wrap gap-x-2 gap-y-0.5 text-[0.55rem] text-[var(--muted-foreground)]">
        {pts.map((p) => (
          <li key={p.m.model} className="flex items-center gap-1">
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: POINT_COLORS[p.i % POINT_COLORS.length] }}
            />
            {shortModel(p.m.model)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Pass-rate per model, banded bars. */
function ScoreBars({ models }: { models: ModelStat[] }) {
  const tq = useTranslations("quality");
  if (models.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  return (
    <div className="flex h-24 items-end gap-2">
      {models.map((m) => (
        <div key={m.model} className="flex flex-1 flex-col items-center gap-0.5">
          <span className="text-[0.55rem] tabular-nums">{fmtScore(m.pass_rate)}</span>
          <div
            className="w-full rounded-sm"
            style={{
              height: `${Math.max(4, m.pass_rate * 72)}px`,
              background: scoreBand(m.pass_rate),
            }}
          />
          <span className="max-w-full truncate text-[0.5rem] text-[var(--muted-foreground)]">
            {shortModel(m.model)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Non-regression retention per model, horizontal bars. */
function NonRegBars({ models }: { models: ModelStat[] }) {
  const tq = useTranslations("quality");
  const rows = models.filter((m) => m.non_regression != null);
  if (rows.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  return (
    <div className="flex flex-col gap-1">
      {rows.map((m) => {
        const v = m.non_regression ?? 0;
        const tone = v >= 0.95 ? "#34d399" : v >= 0.8 ? "#f59e0b" : "#f87171";
        return (
          <div key={m.model} className="flex items-center gap-1.5 text-[0.6rem]">
            <span className="w-20 shrink-0 truncate text-[var(--muted-foreground)]">
              {shortModel(m.model)}
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-sm bg-[var(--muted)]/40">
              <div
                className="h-full rounded-sm"
                style={{ width: `${v * 100}%`, background: tone }}
              />
            </div>
            <span className="w-8 shrink-0 text-right tabular-nums">{Math.round(v * 100)}%</span>
          </div>
        );
      })}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-[0.72rem] font-medium text-[var(--muted-foreground)]">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-1">{children}</CardContent>
    </Card>
  );
}

// ──────────────────────────────── the board ──────────────────────────────────

/** Full Comparaison des modèles board (reference image 04) — real data only. */
export function ModelsBoard({
  comparison,
  calibration,
}: {
  comparison: ModelComparison | undefined;
  calibration: Calibration | undefined;
  release: ReleaseStatus | undefined;
}) {
  const tq = useTranslations("quality");
  const models = comparison?.models ?? [];
  return (
    <div className="flex flex-col gap-2">
      <ModelsKpis comparison={comparison} calibration={calibration} />
      <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
        <ChartCard title={tq("models.charts.scoreByModel")}>
          <ScoreBars models={models} />
        </ChartCard>
        <ChartCard title={tq("models.charts.faithGrounding")}>
          <ModelScatter
            models={models}
            x={(m) => m.faithfulness}
            y={(m) => m.grounding}
            xLabel={tq("models.kpi.faithfulness")}
            yLabel={tq("models.kpi.grounding")}
          />
        </ChartCard>
        <ChartCard title={tq("models.charts.costQuality")}>
          <ModelScatter
            models={models}
            x={(m) => m.est_cost_eur ?? 0}
            y={(m) => m.pass_rate}
            xLabel={tq("models.cols.cost")}
            yLabel={tq("models.cols.score")}
          />
        </ChartCard>
        <ChartCard title={tq("models.charts.nonReg")}>
          <NonRegBars models={models} />
        </ChartCard>
      </div>
      <ModelsTable comparison={comparison} />
    </div>
  );
}

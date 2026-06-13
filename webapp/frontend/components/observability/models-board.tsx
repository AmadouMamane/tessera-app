"use client";

import {
  Activity,
  Award,
  Coins,
  Crosshair,
  Gauge,
  Layers,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  Calibration,
  JudgeConsensus,
  JudgeDrift,
  ModelComparison,
  ModelStat,
  ReleaseStatus,
  RunRegistry,
} from "@/lib/api/schemas";

const DASH = "—";

const CATEGORIES = [
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
] as const;

const LINE_COLORS = ["#34d399", "#60a5fa", "#f59e0b", "#a78bfa", "#f87171", "#22d3ee"];

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
  return eur === 0 ? "0 €" : `${eur.toFixed(2).replace(".", ",")} €`;
}
function useCatLabel() {
  const tq = useTranslations("quality");
  return (c: string) =>
    (CATEGORIES as readonly string[]).includes(c) ? tq(`failed.cat.${c}`) : c.replace(/_/g, " ");
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
      <span className="flex items-center gap-1 text-[0.62rem] text-[var(--muted-foreground)]">
        <span className="opacity-70">{icon}</span>
        {label}
      </span>
      <span className={`text-lg font-semibold leading-tight tabular-nums ${tone ?? ""}`}>
        {value}
      </span>
      {sub ? <span className="text-[0.58rem] text-[var(--muted-foreground)]">{sub}</span> : null}
    </Card>
  );
}

function evoDelta(evo: number[] | undefined): number | null {
  if (!evo || evo.length < 2) return null;
  const last = evo[evo.length - 1];
  const prev = evo[evo.length - 2];
  if (last == null || prev == null) return null;
  return last - prev;
}

function DeltaSub({ delta }: { delta: number | null }) {
  const tq = useTranslations("quality");
  if (delta == null) return <>{tq("models.kpi.vsPrev", { d: DASH })}</>;
  const pts = Math.round(delta * 100);
  const tone = pts > 0 ? "text-emerald-500" : pts < 0 ? "text-red-500" : "";
  return (
    <span className={tone}>
      {pts > 0 ? "+" : ""}
      {pts} {tq("models.kpi.pts")}
    </span>
  );
}

function ModelsKpis({
  comparison,
  calibration,
  release,
}: {
  comparison: ModelComparison | undefined;
  calibration: Calibration | undefined;
  release: ReleaseStatus | undefined;
}) {
  const tq = useTranslations("quality");
  const models = comparison?.models ?? [];
  const ref = models[0];
  const kappa = calibration?.kappa;
  const nonReg = release?.non_regression_rate;
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
      <Kpi
        icon={<Award className="h-3.5 w-3.5" />}
        label={tq("models.kpi.referent")}
        value={ref ? shortModel(ref.model) : DASH}
        sub={
          ref ? (
            <Badge tone="success" className="text-[0.52rem]">
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
        icon={<ShieldCheck className="h-3.5 w-3.5" />}
        label={tq("models.kpi.nonReg")}
        value={pctOrDash(nonReg)}
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

// ───────────────────────────── score over time ───────────────────────────────

/** Multi-line of per-model pass-rate evolution (oldest→newest run). */
function ScoreLines({ models }: { models: ModelStat[] }) {
  const tq = useTranslations("quality");
  const series = models.filter((m) => (m.evolution?.length ?? 0) >= 2);
  if (series.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  const w = 220;
  const h = 96;
  const maxLen = Math.max(...series.map((m) => m.evolution?.length ?? 0));
  return (
    <div className="flex flex-col gap-1">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="h-24 w-full"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {[0.25, 0.5, 0.75].map((g) => (
          <line
            key={g}
            x1="0"
            y1={h - g * h}
            x2={w}
            y2={h - g * h}
            stroke="var(--border)"
            strokeWidth="0.5"
          />
        ))}
        {series.map((m, mi) => {
          const evo = m.evolution ?? [];
          const d = evo
            .map((v, i) => {
              const x = (i / Math.max(1, maxLen - 1)) * w;
              const y = h - 4 - v * (h - 8);
              return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
            })
            .join(" ");
          return (
            <path
              key={m.model}
              d={d}
              fill="none"
              stroke={LINE_COLORS[mi % LINE_COLORS.length]}
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          );
        })}
      </svg>
      <ModelLegend models={series} />
    </div>
  );
}

function ModelLegend({ models }: { models: ModelStat[] }) {
  return (
    <ul className="flex flex-wrap gap-x-2 gap-y-0.5 text-[0.55rem] text-[var(--muted-foreground)]">
      {models.map((m, i) => (
        <li key={m.model} className="flex items-center gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: LINE_COLORS[i % LINE_COLORS.length] }}
          />
          {shortModel(m.model)}
        </li>
      ))}
    </ul>
  );
}

// ──────────────────────────────── radar ──────────────────────────────────────

/** Quality radar: one polygon per model over five normalised axes. */
function QualityRadar({ models }: { models: ModelStat[] }) {
  const tq = useTranslations("quality");
  const axes: { key: string; get: (m: ModelStat) => number | null | undefined }[] = [
    { key: tq("models.radar.score"), get: (m) => m.pass_rate },
    { key: tq("models.radar.faith"), get: (m) => m.faithfulness },
    { key: tq("models.radar.grounding"), get: (m) => m.grounding },
    { key: tq("models.radar.nonReg"), get: (m) => m.non_regression },
    { key: tq("models.radar.antiHallu"), get: (m) => m.hallucination },
  ];
  const usable = models.slice(0, 6);
  if (usable.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  const cx = 60;
  const cy = 56;
  const r = 42;
  const n = axes.length;
  const point = (axisIdx: number, value: number): [number, number] => {
    const angle = -Math.PI / 2 + (axisIdx / n) * 2 * Math.PI;
    return [cx + Math.cos(angle) * r * value, cy + Math.sin(angle) * r * value];
  };
  return (
    <div className="flex items-center gap-2">
      <svg viewBox="0 0 120 112" className="h-28 w-28 shrink-0" aria-hidden="true">
        {[0.33, 0.66, 1].map((g) => (
          <polygon
            key={g}
            points={axes.map((_, i) => point(i, g).join(",")).join(" ")}
            fill="none"
            stroke="var(--border)"
            strokeWidth="0.5"
          />
        ))}
        {usable.map((m, mi) => {
          const pts = axes
            .map((a, i) => point(i, Math.max(0, Math.min(1, a.get(m) ?? 0))).join(","))
            .join(" ");
          const c = LINE_COLORS[mi % LINE_COLORS.length];
          return (
            <polygon
              key={m.model}
              points={pts}
              fill={c}
              fillOpacity="0.08"
              stroke={c}
              strokeWidth="1"
            />
          );
        })}
      </svg>
      <ul className="flex flex-col gap-0.5 text-[0.55rem] text-[var(--muted-foreground)]">
        {axes.map((a) => (
          <li key={a.key}>{a.key}</li>
        ))}
      </ul>
    </div>
  );
}

// ──────────────────────────── category heatmap ───────────────────────────────

function heatColor(rate: number): string {
  if (rate >= 0.8) return "rgba(52,211,153,0.85)";
  if (rate >= 0.5) return "rgba(245,158,11,0.85)";
  return "rgba(248,113,113,0.85)";
}

/** Pass-rate per model × failure category as a coloured grid. */
function CategoryHeatmap({ models }: { models: ModelStat[] }) {
  const tq = useTranslations("quality");
  const catLabel = useCatLabel();
  const present = CATEGORIES.filter((c) => models.some((m) => m.categories?.[c] != null));
  if (models.length === 0 || present.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="text-[0.55rem]">
        <thead>
          <tr>
            <th className="pr-1 text-left font-medium text-[var(--muted-foreground)]" />
            {present.map((c) => (
              <th
                key={c}
                className="px-0.5 pb-1 text-center font-normal text-[var(--muted-foreground)]"
              >
                <span className="block w-7 truncate" title={catLabel(c)}>
                  {catLabel(c).slice(0, 4)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr key={m.model}>
              <td className="pr-1 text-[var(--muted-foreground)]">{shortModel(m.model)}</td>
              {present.map((c) => {
                const v = m.categories?.[c];
                return (
                  <td key={c} className="p-0.5">
                    <span
                      className="flex h-4 w-7 items-center justify-center rounded-[2px] text-[0.5rem] text-black/70"
                      style={{ background: v == null ? "var(--muted)" : heatColor(v) }}
                      title={`${catLabel(c)}: ${v == null ? DASH : `${Math.round(v * 100)}%`}`}
                    >
                      {v == null ? "" : Math.round(v * 100)}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ──────────────────────────────── scatters ───────────────────────────────────

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
  const [xMin, xMax, yMin, yMax] = [
    Math.min(...xs),
    Math.max(...xs),
    Math.min(...ys),
    Math.max(...ys),
  ];
  const w = 200;
  const h = 96;
  const px = (v: number) => 8 + ((v - xMin) / (xMax - xMin || 1)) * (w - 16);
  const py = (v: number) => h - 16 - ((v - yMin) / (yMax - yMin || 1)) * (h - 26);
  return (
    <div className="flex flex-col gap-1">
      <svg viewBox={`0 0 ${w} ${h}`} className="h-24 w-full" aria-hidden="true">
        {pts.map((p) => (
          <circle
            key={p.m.model}
            cx={px(p.xv)}
            cy={py(p.yv)}
            r={3}
            fill={LINE_COLORS[p.i % LINE_COLORS.length]}
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
      <ModelLegend models={pts.map((p) => p.m)} />
    </div>
  );
}

// ───────────────────────── pass-rate of recent runs ──────────────────────────

function parseRunAt(stamp: string): number {
  const m = stamp.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/);
  if (!m) return 0;
  const g = (i: number) => Number(m[i] ?? 0);
  return Date.UTC(g(1), g(2) - 1, g(3), g(4), g(5), g(6));
}
function fmtDay(stamp: string): string {
  const t = parseRunAt(stamp);
  if (!t) return stamp;
  const dt = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(dt.getUTCDate())}/${p(dt.getUTCMonth() + 1)}`;
}

function PassRateRuns({ registry }: { registry: RunRegistry | undefined }) {
  const tq = useTranslations("quality");
  const runs = [...(registry?.runs ?? [])]
    .filter((r) => r.total >= 10)
    .sort((a, b) => parseRunAt(b.run_at) - parseRunAt(a.run_at))
    .slice(0, 7);
  if (runs.length === 0)
    return <p className="text-[0.7rem] text-[var(--muted-foreground)]">{tq("models.noData")}</p>;
  return (
    <table className="w-full text-left text-[0.65rem]">
      <thead className="text-[0.58rem] uppercase tracking-wide text-[var(--muted-foreground)]">
        <tr className="border-b border-[var(--border)]">
          <th className="py-1 pr-2 font-medium">{tq("models.runs.model")}</th>
          <th className="py-1 pr-2 text-right font-medium">{tq("models.runs.cases")}</th>
          <th className="py-1 pr-2 text-right font-medium">{tq("models.runs.passed")}</th>
          <th className="py-1 pr-2 text-right font-medium">{tq("models.runs.rate")}</th>
          <th className="py-1 pr-2 font-medium">{tq("models.runs.date")}</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((r) => (
          <tr key={r.run_id} className="border-b border-[var(--border)]/50">
            <td className="py-1 pr-2 font-medium">{shortModel(r.model)}</td>
            <td className="py-1 pr-2 text-right tabular-nums">{r.total}</td>
            <td className="py-1 pr-2 text-right tabular-nums">{r.passed}</td>
            <td
              className="py-1 pr-2 text-right font-semibold tabular-nums"
              style={{ color: scoreBand(r.pass_rate) }}
            >
              {Math.round(r.pass_rate * 100)}%
            </td>
            <td className="py-1 pr-2 tabular-nums text-[var(--muted-foreground)]">
              {fmtDay(r.run_at)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ─────────────────────────── regressions by model ────────────────────────────

function RegressionsByModel({ release }: { release: ReleaseStatus | undefined }) {
  const tq = useTranslations("quality");
  const regs = release?.regressions ?? [];
  if (regs.length === 0)
    return (
      <p className="py-4 text-center text-[0.7rem] text-emerald-500">
        {tq("models.noRegressions")}
      </p>
    );
  const max = Math.max(...regs.map((r) => Math.abs(r.delta)), 0.1);
  return (
    <div className="flex flex-col gap-1.5">
      {regs.map((r) => (
        <div
          key={`${r.model}-${r.last_run_at}`}
          className="flex items-center gap-1.5 text-[0.6rem]"
        >
          <span className="w-20 shrink-0 truncate text-[var(--muted-foreground)]">
            {shortModel(r.model)}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-sm bg-[var(--muted)]/40">
            <div
              className="h-full rounded-sm bg-red-500"
              style={{ width: `${(Math.abs(r.delta) / max) * 100}%` }}
            />
          </div>
          <span className="w-20 shrink-0 text-right tabular-nums text-red-500">
            {Math.round(r.prev_rate * 100)}→{Math.round(r.last_rate * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────── drift & stability ───────────────────────────

function DriftKpi({ label, value, level }: { label: string; value: string; level: string | null }) {
  const tq = useTranslations("quality");
  const tone =
    level == null
      ? ""
      : ["high", "critical"].includes(level)
        ? "text-red-500"
        : level === "moderate"
          ? "text-amber-500"
          : "text-emerald-500";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[0.58rem] text-[var(--muted-foreground)]">{label}</span>
      <span className={`text-base font-semibold tabular-nums ${tone}`}>{value}</span>
      {level ? (
        <span className="text-[0.55rem] text-[var(--muted-foreground)]">
          {tq(`models.drift.${level}`)}
        </span>
      ) : null}
    </div>
  );
}

function fmtDiv(d: number | null | undefined): string {
  return d == null ? DASH : d.toFixed(3);
}

function DriftStability({
  faithDrift,
  groundingDrift,
  consensus,
  models,
}: {
  faithDrift: JudgeDrift | undefined;
  groundingDrift: JudgeDrift | undefined;
  consensus: JudgeConsensus | undefined;
  models: ModelStat[];
}) {
  const tq = useTranslations("quality");
  const disagree = consensus?.consensus_rate != null ? 1 - consensus.consensus_rate : null;
  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-3 gap-2">
        <DriftKpi
          label={tq("models.drift.faith")}
          value={fmtDiv(faithDrift?.divergence)}
          level={faithDrift?.level ?? null}
        />
        <DriftKpi
          label={tq("models.drift.ground")}
          value={fmtDiv(groundingDrift?.divergence)}
          level={groundingDrift?.level ?? null}
        />
        <DriftKpi
          label={tq("models.drift.consistency")}
          value={disagree == null ? DASH : `${Math.round(disagree * 100)}%`}
          level={disagree == null ? null : disagree >= 0.2 ? "moderate" : "stable"}
        />
      </div>
      <ScoreLines models={models} />
    </div>
  );
}

// ──────────────────────────── detailed comparison ────────────────────────────

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

// ───────────────────────────────── helpers ───────────────────────────────────

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

/** Honest "no real source" panel — Tessera has no per-model×intent labels. */
function IntentUnavailable() {
  const tq = useTranslations("quality");
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-[0.72rem] font-medium text-[var(--muted-foreground)]">
          {tq("models.intent.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center justify-center gap-1 py-6 text-center">
        <Layers className="h-5 w-5 text-[var(--muted-foreground)] opacity-40" />
        <p className="text-[0.65rem] text-[var(--muted-foreground)]">
          {tq("models.intent.unavailable")}
        </p>
      </CardContent>
    </Card>
  );
}

// ──────────────────────────────── the board ──────────────────────────────────

/** Full Comparaison des modèles board (reference image 04) — real data only. */
export function ModelsBoard({
  comparison,
  calibration,
  release,
  registry,
  faithDrift,
  groundingDrift,
  consensus,
}: {
  comparison: ModelComparison | undefined;
  calibration: Calibration | undefined;
  release: ReleaseStatus | undefined;
  registry: RunRegistry | undefined;
  faithDrift: JudgeDrift | undefined;
  groundingDrift: JudgeDrift | undefined;
  consensus: JudgeConsensus | undefined;
}) {
  const tq = useTranslations("quality");
  const models = comparison?.models ?? [];
  return (
    <div className="flex flex-col gap-2">
      <ModelsKpis comparison={comparison} calibration={calibration} release={release} />

      {/* Row 1: score over time · radar · category heatmap · faith×grounding */}
      <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
        <ChartCard title={tq("models.charts.scoreByModel")}>
          <ScoreLines models={models} />
        </ChartCard>
        <ChartCard title={tq("models.charts.radar")}>
          <QualityRadar models={models} />
        </ChartCard>
        <ChartCard title={tq("models.charts.heatmap")}>
          <CategoryHeatmap models={models} />
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
      </div>

      {/* Row 2: detailed table · performance par intent (unavailable) · cost×quality */}
      <div className="grid gap-2 2xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)]">
        <ModelsTable comparison={comparison} />
        <IntentUnavailable />
        <ChartCard title={tq("models.charts.costQuality")}>
          <ModelScatter
            models={models}
            x={(m) => m.est_cost_eur ?? 0}
            y={(m) => m.pass_rate}
            xLabel={tq("models.cols.cost")}
            yLabel={tq("models.cols.score")}
          />
        </ChartCard>
      </div>

      {/* Row 3: recent runs · regressions by model · drift & stability */}
      <div className="grid gap-2 2xl:grid-cols-3">
        <ChartCard title={tq("models.charts.recentRuns")}>
          <PassRateRuns registry={registry} />
        </ChartCard>
        <ChartCard title={tq("models.charts.regressions")}>
          <RegressionsByModel release={release} />
        </ChartCard>
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="flex items-center gap-1.5 text-[0.72rem] font-medium text-[var(--muted-foreground)]">
              <Activity className="h-3.5 w-3.5" />
              {tq("models.charts.drift")}
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-1">
            <DriftStability
              faithDrift={faithDrift}
              groundingDrift={groundingDrift}
              consensus={consensus}
              models={models}
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

"use client";

import {
  Download,
  FileText,
  GitCompareArrows,
  type LucideIcon,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Calibration, CalibrationPoint, JudgeConsensus, JudgeDrift } from "@/lib/api/schemas";

const MATCH = "#10b981";
const MISS = "#ef4444";
const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";

/** A compact KPI tile for the calibration headline strip (image normative). */
function Kpi({
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
      {hint ? (
        <div className="truncate text-[0.65rem] text-[var(--muted-foreground)]">{hint}</div>
      ) : null}
    </Card>
  );
}

/** 2×2 confusion matrix (judge × human reference) built from the gold points. */
function ConfusionMatrix({
  tp,
  fp,
  fn,
  tn,
}: {
  tp: number;
  fp: number;
  fn: number;
  tn: number;
}) {
  const tq = useTranslations("quality");
  const total = tp + fp + fn + tn || 1;
  const cell = (n: number, diag: boolean) => (
    <td className="border border-[var(--tessera-border)] px-3 py-2 text-center">
      <span className={`font-semibold tabular-nums ${diag ? GOOD : n > 0 ? BAD : MUTED}`}>{n}</span>
      <span className="block text-[0.65rem] text-[var(--muted-foreground)]">
        {Math.round((n / total) * 100)}%
      </span>
    </td>
  );
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-[0.7rem] text-[var(--muted-foreground)]">
          <th className="px-2 py-1" />
          <th className="px-2 py-1 font-medium" colSpan={2}>
            {tq("judge.refHuman")}
          </th>
        </tr>
        <tr className="text-[0.7rem] text-[var(--muted-foreground)]">
          <th className="px-2 py-1" />
          <th className="px-2 py-1 font-medium">{tq("judge.humanGood")}</th>
          <th className="px-2 py-1 font-medium">{tq("judge.humanBad")}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th className="px-2 py-1 text-left text-[0.7rem] font-medium text-[var(--muted-foreground)]">
            {tq("judge.correct")}
          </th>
          {cell(tp, true)}
          {cell(fp, false)}
        </tr>
        <tr>
          <th className="px-2 py-1 text-left text-[0.7rem] font-medium text-[var(--muted-foreground)]">
            {tq("judge.incorrect")}
          </th>
          {cell(fn, false)}
          {cell(tn, true)}
        </tr>
      </tbody>
    </table>
  );
}

/** Histogram of judge scores in five bins. */
function ScoreDistribution({ points }: { points: CalibrationPoint[] }) {
  const bins = [0, 0, 0, 0, 0];
  for (const p of points) {
    const idx = Math.min(4, Math.max(0, Math.floor(p.judge_score * 5)));
    bins[idx] = (bins[idx] ?? 0) + 1;
  }
  const max = Math.max(1, ...bins);
  return (
    <div className="flex h-40 items-end gap-2">
      {bins.map((c, i) => (
        <div key={(i * 0.2).toFixed(1)} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-[0.65rem] tabular-nums text-[var(--muted-foreground)]">{c}</span>
          <div
            className="w-full rounded-t bg-blue-500/70"
            style={{ height: `${(c / max) * 100}%`, minHeight: c > 0 ? "4px" : "0" }}
          />
          <span className="text-[0.6rem] tabular-nums text-[var(--muted-foreground)]">
            {(i * 0.2).toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Reliability curve: mean judge score (x) vs observed good-rate (y) per bin,
 *  against the ideal diagonal. A well-calibrated judge tracks the diagonal. */
function CalibrationCurve({ points }: { points: CalibrationPoint[] }) {
  const tq = useTranslations("quality");
  if (points.length === 0)
    return (
      <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">
        {tq("judge.noData")}
      </p>
    );
  // Bin by judge score; each bin → (mean score, fraction whose human label is good).
  const bins = new Map<number, { sum: number; good: number; n: number }>();
  for (const p of points) {
    const b = Math.min(4, Math.max(0, Math.floor(p.judge_score * 5)));
    const cur = bins.get(b) ?? { sum: 0, good: 0, n: 0 };
    cur.sum += p.judge_score;
    cur.good += p.human_label === "good" ? 1 : 0;
    cur.n += 1;
    bins.set(b, cur);
  }
  const pts = [...bins.values()]
    .map((v) => ({ x: v.sum / v.n, y: v.good / v.n }))
    .sort((a, b) => a.x - b.x);
  const W = 160;
  const H = 120;
  const px = (v: number) => 8 + v * (W - 16);
  const py = (v: number) => H - 12 - v * (H - 20);
  const line = pts
    .map((p, i) => `${i === 0 ? "M" : "L"}${px(p.x).toFixed(1)},${py(p.y).toFixed(1)}`)
    .join(" ");
  return (
    <div className="flex flex-col gap-1">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-32 w-full" aria-hidden="true">
        <line
          x1={px(0)}
          y1={py(0)}
          x2={px(1)}
          y2={py(1)}
          stroke="var(--border)"
          strokeWidth="1"
          strokeDasharray="3 3"
        />
        {pts.length >= 2 ? (
          <path d={line} fill="none" stroke="#60a5fa" strokeWidth="1.5" strokeLinejoin="round" />
        ) : null}
        {pts.map((p) => (
          <circle key={`${p.x}-${p.y}`} cx={px(p.x)} cy={py(p.y)} r="2.5" fill="#60a5fa" />
        ))}
        <text
          x={W / 2}
          y={H - 1}
          textAnchor="middle"
          className="fill-[var(--muted-foreground)] text-[6px]"
        >
          {tq("judge.curveX")}
        </text>
        <text x={2} y={8} className="fill-[var(--muted-foreground)] text-[6px]">
          {tq("judge.curveY")}
        </text>
      </svg>
      <div className="flex gap-3 text-[0.55rem] text-[var(--muted-foreground)]">
        <span className="flex items-center gap-1">
          <span className="h-1.5 w-3 rounded-full bg-[#60a5fa]" />
          {tq("judge.curveActual")}
        </span>
        <span className="flex items-center gap-1">
          <span className="h-px w-3 border-t border-dashed border-[var(--muted-foreground)]" />
          {tq("judge.curveIdeal")}
        </span>
      </div>
    </div>
  );
}

/** Verbosity-bias scatter: answer length (x) vs judge score (y), coloured by agreement. */
function VerbosityScatter({ points }: { points: CalibrationPoint[] }) {
  const tq = useTranslations("quality");
  const H = 52;
  const top = 4;
  const maxLen = Math.max(1, ...points.map((p) => p.length));
  return (
    <div className="flex flex-col gap-1">
      <div className="relative h-40 w-full">
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
          {points.map((p, i) => (
            <circle
              key={`${p.question}-${i}`}
              cx={2 + (p.length / maxLen) * 96}
              cy={top + (1 - p.judge_score) * H}
              r={1.4}
              fill={p.match ? MATCH : MISS}
            />
          ))}
        </svg>
      </div>
      <div className="flex justify-between text-[0.65rem] text-[var(--muted-foreground)]">
        <span>↑ {tq("judge.cols.score")}</span>
        <span>{tq("judge.lengthAxis")} →</span>
      </div>
    </div>
  );
}

/** Horizontal band gauge: a segmented track with a marker at the value, the
 * "Stable→Critique" / "Trop sévère↔Trop permissif" arcs of the normative tab. */
function BandGauge({
  pct,
  segments,
  leftLabel,
  rightLabel,
}: {
  pct: number | null; // marker position 0..1 (null ⇒ unknown, no marker)
  segments: { frac: number; color: string; label?: string }[];
  leftLabel?: string;
  rightLabel?: string;
}) {
  const hasLabels = segments.some((s) => s.label);
  return (
    <div className="flex flex-col gap-1.5">
      <div className="relative py-1">
        <div className="flex h-2 w-full overflow-hidden rounded-full">
          {segments.map((s, i) => (
            <div
              key={`${s.color}-${i}`}
              style={{ flexBasis: `${s.frac * 100}%`, background: s.color }}
            />
          ))}
        </div>
        {pct != null ? (
          <div
            className="absolute top-0 h-4 w-4 -translate-x-1/2 rounded-full border-2 border-[var(--tessera-surface)] bg-[var(--tessera-text)] shadow"
            style={{ left: `${Math.max(0, Math.min(1, pct)) * 100}%` }}
          />
        ) : null}
      </div>
      {leftLabel || rightLabel ? (
        <div className="flex justify-between text-[0.65rem] text-[var(--muted-foreground)]">
          <span>{leftLabel}</span>
          <span>{rightLabel}</span>
        </div>
      ) : null}
      {hasLabels ? (
        <div className="flex justify-between text-[0.6rem]">
          {segments.map((s, i) =>
            s.label ? (
              <span key={`${s.color}-${i}-l`} style={{ color: s.color }}>
                {s.label}
              </span>
            ) : null,
          )}
        </div>
      ) : null}
    </div>
  );
}

/** Full judge-calibration hero, faithful to the normative tab (image 05):
 * KPI strip · confusion matrix · score distribution · verbosity-bias scatter ·
 * ambiguous cases · judge profile + calibration actions. All real: the gold-set
 * points feed the matrix/scatter/bias, `drift` comes from the durable score log
 * (GET /observability/judge-drift) and `consensus` from a live local judge panel
 * (GET /observability/judge-consensus). */
export function JudgeCalibration({
  data,
  drift,
  consensus,
  loading,
}: {
  data: Calibration | undefined;
  drift?: JudgeDrift;
  consensus?: JudgeConsensus;
  loading: boolean;
}) {
  const tq = useTranslations("quality");

  if (loading && !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("judge.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.available) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("judge.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("judge.unavailable")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const points = data.points ?? [];
  const total = points.length || 1;
  // Confusion matrix from the gold points (judge label × human label).
  const tp = points.filter((p) => p.judge_label === "good" && p.human_label === "good").length;
  const fp = points.filter((p) => p.judge_label === "good" && p.human_label !== "good").length;
  const fn = points.filter((p) => p.judge_label !== "good" && p.human_label === "good").length;
  const tn = points.filter((p) => p.judge_label !== "good" && p.human_label !== "good").length;
  const fpRate = fp / total;
  const fnRate = fn / total;
  // Severity bias: judge mean score minus human pass-rate (>0 ⇒ lenient/permissive).
  const meanScore = points.reduce((s, p) => s + p.judge_score, 0) / total;
  const humanGoodRate = points.filter((p) => p.human_label === "good").length / total;
  const severityBias = points.length > 0 ? meanScore - humanGoodRate : null;
  const verbosity = data.verbosity_corr ?? 0;
  const kappa = data.kappa ?? 0;
  const disagreements = points.filter((p) => !p.match);

  const kappaTone = kappa >= 0.8 ? GOOD : kappa >= 0.6 ? WARN : BAD;
  const verbTone = Math.abs(verbosity) < 0.2 ? GOOD : Math.abs(verbosity) < 0.4 ? WARN : BAD;
  const verbHint =
    Math.abs(verbosity) < 0.2
      ? tq("judge.low")
      : Math.abs(verbosity) < 0.4
        ? tq("judge.moderate")
        : tq("judge.strong");
  const sevTone = severityBias == null ? MUTED : Math.abs(severityBias) < 0.1 ? GOOD : WARN;
  const matches = total - disagreements.length;

  // Judge drift (real, from the durable score log) and multi-judge consensus
  // (real, from the local judge panel) — null/unknown when their source is absent.
  const driftDiv = drift?.divergence ?? null;
  const driftLevel = drift?.level ?? "unknown";
  const driftLabel = tq(
    `judge.drift${driftLevel.charAt(0).toUpperCase()}${driftLevel.slice(1)}` as "judge.driftStable",
  );
  const driftTone =
    driftDiv == null
      ? MUTED
      : driftLevel === "stable" || driftLevel === "low"
        ? GOOD
        : driftLevel === "moderate"
          ? WARN
          : BAD;
  const consensusOk = consensus?.available === true;
  const consensusRate = consensusOk ? (consensus?.consensus_rate ?? null) : null;

  // Band-gauge marker positions (the normative "arc"). Drift maps 0..0.25 across
  // Stable→Critique; severity maps -0.6..+0.6 across Trop sévère↔Trop permissif.
  const _DRIFT_MAX = 0.25;
  const driftPct = driftDiv == null ? null : driftDiv / _DRIFT_MAX;
  const driftDelta = drift?.delta ?? null;
  const _SEV_RANGE = 0.6;
  const sevPct = severityBias == null ? null : (severityBias + _SEV_RANGE) / (2 * _SEV_RANGE);
  const driftSegments = [
    { frac: 0.12, color: "#10b981", label: tq("judge.driftStable") },
    { frac: 0.12, color: "#65a30d", label: tq("judge.driftLow") },
    { frac: 0.24, color: "#f59e0b", label: tq("judge.driftModerate") },
    { frac: 0.32, color: "#f97316", label: tq("judge.driftHigh") },
    { frac: 0.2, color: "#ef4444", label: tq("judge.driftCritical") },
  ];
  const sevSegments = [
    { frac: 1 / 3, color: "#ef4444" },
    { frac: 1 / 3, color: "#10b981" },
    { frac: 1 / 3, color: "#f59e0b" },
  ];

  function exportCalibration() {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tessera-judge-calibration-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-3">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Kpi
          label={tq("judge.kappaTitle")}
          value={kappa.toFixed(2)}
          tone={kappaTone}
          hint={`κ Cohen · ${kappa >= 0.8 ? tq("judge.excellent") : tq("judge.moderate")}`}
        />
        <Kpi
          label={tq("judge.agreementGlobal")}
          value={data.agreement == null ? "—" : `${Math.round(data.agreement * 100)}%`}
          tone={data.agreement != null && data.agreement >= 0.8 ? GOOD : WARN}
        />
        <Kpi
          label={tq("judge.fp")}
          value={`${(fpRate * 100).toFixed(1)}%`}
          tone={fpRate < 0.05 ? GOOD : WARN}
          hint={`${fp}/${total}`}
        />
        <Kpi
          label={tq("judge.fn")}
          value={`${(fnRate * 100).toFixed(1)}%`}
          tone={fnRate < 0.05 ? GOOD : WARN}
          hint={`${fn}/${total}`}
        />
        <Kpi
          label={tq("judge.verbosityBias")}
          value={verbosity.toFixed(2)}
          tone={verbTone}
          hint={verbHint}
        />
        <Kpi
          label={tq("judge.severityBias")}
          value={
            severityBias == null ? "—" : `${severityBias >= 0 ? "+" : ""}${severityBias.toFixed(2)}`
          }
          tone={sevTone}
          hint={
            severityBias == null
              ? undefined
              : severityBias > 0
                ? tq("judge.tooLenient")
                : tq("judge.tooStrict")
          }
        />
        <Kpi
          label={tq("judge.drift")}
          value={driftDiv == null ? "—" : driftDiv.toFixed(2)}
          tone={driftTone}
          hint={driftLabel}
        />
        <Kpi
          label={tq("judge.consensus")}
          value={consensusRate == null ? "—" : `${Math.round(consensusRate * 100)}%`}
          tone={consensusRate != null && consensusRate >= 0.8 ? GOOD : WARN}
          hint={
            consensusOk && consensus?.n_judges
              ? tq("judge.consensusJudges", { n: consensus.n_judges })
              : undefined
          }
        />
      </div>

      {/* Confusion matrix · calibration curve · distribution · verbosity scatter */}
      <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.confusion")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ConfusionMatrix tp={tp} fp={fp} fn={fn} tn={tn} />
            <div className="mt-2 flex flex-wrap gap-x-4 text-[0.7rem] text-[var(--muted-foreground)]">
              <span>
                {tq("judge.fp")}: <span className={BAD}>{fp}</span>
              </span>
              <span>
                {tq("judge.fn")}: <span className={BAD}>{fn}</span>
              </span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.curve")}</CardTitle>
          </CardHeader>
          <CardContent>
            <CalibrationCurve points={points} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.distribution")}</CardTitle>
          </CardHeader>
          <CardContent>
            {points.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">—</p>
            ) : (
              <ScoreDistribution points={points} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.verbScatter")}</CardTitle>
          </CardHeader>
          <CardContent>
            {points.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">—</p>
            ) : (
              <>
                <VerbosityScatter points={points} />
                <p className="mt-1 text-[0.7rem] text-[var(--muted-foreground)]">
                  {tq("judge.verbCorr")} :{" "}
                  <span className={`tabular-nums ${verbTone}`}>{verbosity.toFixed(2)}</span> ·{" "}
                  {verbHint}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Band gauges (the normative "arc"): severity bias and judge drift */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.severityBias")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex items-end gap-2">
              <span className={`font-serif text-2xl font-semibold tabular-nums ${sevTone}`}>
                {severityBias == null
                  ? "—"
                  : `${severityBias >= 0 ? "+" : ""}${severityBias.toFixed(2)}`}
              </span>
              <span className="pb-1 text-xs text-[var(--muted-foreground)]">
                {severityBias == null
                  ? ""
                  : severityBias > 0
                    ? tq("judge.tooLenient")
                    : tq("judge.tooStrict")}
              </span>
            </div>
            <BandGauge
              pct={sevPct}
              segments={sevSegments}
              leftLabel={tq("judge.tooStrict")}
              rightLabel={tq("judge.tooLenient")}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.drift")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex items-end gap-2">
              <span className={`font-serif text-2xl font-semibold tabular-nums ${driftTone}`}>
                {driftDiv == null ? "—" : driftDiv.toFixed(2)}
              </span>
              <span className="pb-1 text-xs text-[var(--muted-foreground)]">{driftLabel}</span>
              {driftDelta != null ? (
                <span
                  className={`pb-1 text-xs tabular-nums ${driftDelta <= 0 ? GOOD : BAD}`}
                  title={tq("judge.deltaCol")}
                >
                  {driftDelta >= 0 ? "↑" : "↓"} {Math.abs(driftDelta).toFixed(2)}
                </span>
              ) : null}
            </div>
            <BandGauge pct={driftPct} segments={driftSegments} />
          </CardContent>
        </Card>
      </div>

      {/* Ambiguous cases · judge profile + calibration actions */}
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              {tq("judge.ambiguous")}
              <Badge tone={disagreements.length === 0 ? "success" : "warning"}>
                {disagreements.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {disagreements.length === 0 ? (
              <p className="py-4 text-center text-sm text-[var(--muted-foreground)]">
                {tq("judge.noDisagreements")}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                      <th className="py-2 pr-4 font-medium">{tq("judge.cols.case")}</th>
                      <th className="py-2 pr-4 font-medium">{tq("judge.cols.human")}</th>
                      <th className="py-2 pr-4 font-medium">{tq("judge.cols.judge")}</th>
                      <th className="py-2 font-medium">{tq("judge.cols.score")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {disagreements.map((p, i) => (
                      <tr key={`${p.question}-${i}`} className="border-b border-[var(--border)]/50">
                        <td className="py-2 pr-4 text-[var(--muted-foreground)]">
                          <span className="line-clamp-1 max-w-md">{p.question}</span>
                        </td>
                        <td className="py-2 pr-4">{p.human_label}</td>
                        <td className="py-2 pr-4">{p.judge_label}</td>
                        <td className="py-2 tabular-nums">{p.judge_score.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{tq("judge.fiche")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm">
              <Row label={tq("judge.model")}>
                <span className="font-mono text-xs">{data.judge_model ?? "—"}</span>
              </Row>
              <Row label={tq("judge.annotated")}>
                <span className="tabular-nums">{data.n ?? total}</span>
              </Row>
              <Row label={tq("judge.byHumans")}>
                <span className="tabular-nums">{total}</span>
              </Row>
              <Row label={tq("judge.matches")}>
                <Badge tone="success">{matches}</Badge>
              </Row>
              <Row label={tq("judge.lenientNo")}>
                <Badge tone={data.lenient ? "warning" : "success"}>
                  {data.lenient ? tq("judge.lenientYes") : tq("judge.lenientNo")}
                </Badge>
              </Row>
            </CardContent>
          </Card>

          {consensusOk && consensus ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between gap-2 text-sm">
                  {tq("judge.panel")}
                  <Badge tone="neutral">
                    {tq("judge.consensusJudges", { n: consensus.n_judges ?? 0 })}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 text-sm">
                <Row label={tq("judge.consensus")}>
                  <span className="tabular-nums">
                    {Math.round((consensus.consensus_rate ?? 0) * 100)}%
                  </span>
                </Row>
                <Row label={tq("judge.pairwise")}>
                  <span className="tabular-nums">
                    {Math.round((consensus.mean_pairwise_agreement ?? 0) * 100)}%
                  </span>
                </Row>
                <Row label={tq("judge.fleiss")}>
                  <span className="tabular-nums">{(consensus.fleiss_kappa ?? 0).toFixed(2)}</span>
                </Row>
                <div className="mt-1 flex flex-col gap-1.5">
                  {(consensus.per_judge ?? []).map((j) => (
                    <div key={j.judge_model} className="flex items-center gap-2">
                      <span className="w-24 shrink-0 truncate font-mono text-[0.7rem] text-[var(--muted-foreground)]">
                        {j.judge_model}
                      </span>
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--tessera-muted)]">
                        <div
                          className="h-full rounded-full bg-[var(--tessera-green)]"
                          style={{ width: `${Math.round(j.agreement * 100)}%` }}
                        />
                      </div>
                      <span className="w-9 shrink-0 text-right text-[0.7rem] tabular-nums">
                        {Math.round(j.agreement * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">{tq("judge.actions")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1.5">
              <ActionRow icon={RefreshCw} label={tq("judge.recalibrate")} level="admin" />
              <ActionRow icon={GitCompareArrows} label={tq("judge.compare")} level="operator" />
              <ActionRow icon={SlidersHorizontal} label={tq("judge.rubrics")} level="admin" />
              <ActionRow icon={FileText} label={tq("judge.report")} level="operator" />
              <Button
                size="sm"
                variant="outline"
                onClick={exportCalibration}
                className="mt-1 h-8 justify-start gap-2 text-xs"
              >
                <Download className="h-3.5 w-3.5" />
                {tq("judge.export")}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
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

/** A governed calibration action: icon + label + required-role badge. */
function ActionRow({
  icon: Icon,
  label,
  level,
}: {
  icon: LucideIcon;
  label: string;
  level: "operator" | "admin";
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2.5 py-1.5 text-sm">
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <Badge tone={level === "admin" ? "warning" : "success"}>
        {level === "admin" ? "Admin+" : "Operator+"}
      </Badge>
    </div>
  );
}

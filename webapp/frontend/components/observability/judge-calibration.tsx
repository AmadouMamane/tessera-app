"use client";

import {
  Boxes,
  CalendarClock,
  GitCompareArrows,
  Landmark,
  type LucideIcon,
  RefreshCw,
  ShieldCheck,
  Snowflake,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { QInfo } from "@/components/observability/quality-info";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  Calibration,
  CalibrationPoint,
  GroupAgreement,
  JudgeConsensus,
  JudgeDrift,
  ReleaseStatus,
  SeriesBucket,
} from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";
const MATCH = "#10b981";
const MISS = "#ef4444";

/** Stable colour per display category (donut, bars, top-disagreement list). */
const CAT_COLOR: Record<string, string> = {
  faithfulness: "#60a5fa",
  grounding: "#34d399",
  pii: "#f472b6",
  citations: "#fbbf24",
  style: "#a78bfa",
};
const catColor = (c: string) => CAT_COLOR[c] ?? "#94a3b8";

// ── small shared atoms ───────────────────────────────────────────────────────

/** Section heading (A. / B. / C. / D.). */
function Sec({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
      {children}
    </h2>
  );
}

/** A compact KPI tile for the calibration headline strip (image 05, zone A). */
function Kpi({
  label,
  value,
  tone,
  hint,
  hintTone,
  explainKey,
}: {
  label: string;
  value: string;
  tone?: string;
  hint?: string;
  hintTone?: string;
  explainKey?: string;
}) {
  return (
    <Card className="flex flex-col gap-1 p-3">
      <div className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
        <span className="truncate">{label}</span>
        {explainKey ? <QInfo title={label} k={explainKey} className="ml-auto" /> : null}
      </div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
      </div>
      {hint ? <div className={`truncate text-[0.65rem] ${hintTone ?? MUTED}`}>{hint}</div> : null}
    </Card>
  );
}

/** 2×2 confusion matrix (judge × human reference) built from the gold points. */
function ConfusionMatrix({ tp, fp, fn, tn }: { tp: number; fp: number; fn: number; tn: number }) {
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

/** Reliability curve: mean judge score (x) vs observed good-rate (y) per bin. */
function CalibrationCurve({ points }: { points: CalibrationPoint[] }) {
  const tq = useTranslations("quality");
  if (points.length === 0)
    return <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>;
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

/** Histogram of judge scores in five bins, with mean/median footer. */
function ScoreDistribution({ points }: { points: CalibrationPoint[] }) {
  const tq = useTranslations("quality");
  const bins = [0, 0, 0, 0, 0];
  for (const p of points) {
    const idx = Math.min(4, Math.max(0, Math.floor(p.judge_score * 5)));
    bins[idx] = (bins[idx] ?? 0) + 1;
  }
  const max = Math.max(1, ...bins);
  const scores = points.map((p) => p.judge_score).sort((a, b) => a - b);
  const mean = scores.length ? scores.reduce((s, v) => s + v, 0) / scores.length : 0;
  const median = scores.length ? (scores[Math.floor((scores.length - 1) / 2)] ?? 0) : 0;
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex h-36 items-end gap-2">
        {bins.map((c, i) => (
          <div key={(i * 0.2).toFixed(1)} className="flex flex-1 flex-col items-center gap-1">
            <span className="text-[0.6rem] tabular-nums text-[var(--muted-foreground)]">{c}</span>
            <div
              className="w-full rounded-t bg-[#818cf8]/70"
              style={{ height: `${(c / max) * 100}%`, minHeight: c > 0 ? "4px" : "0" }}
            />
            <span className="text-[0.55rem] tabular-nums text-[var(--muted-foreground)]">
              {(i * 0.2).toFixed(1)}
            </span>
          </div>
        ))}
      </div>
      <p className="text-[0.65rem] text-[var(--muted-foreground)]">
        {tq("judge.meanMedian", { m: mean.toFixed(2), md: median.toFixed(2) })}
      </p>
    </div>
  );
}

/** Donut of disagreements per display category. */
function DisagreementDonut({
  data,
  total,
}: {
  data: { label: string; count: number; color: string }[];
  total: number;
}) {
  const tq = useTranslations("quality");
  const R = 40.4;
  const C = 2 * Math.PI * R;
  let offset = 0;
  const arcs =
    total > 0
      ? data.map((d) => {
          const frac = d.count / total;
          const seg = { ...d, dash: frac * C, gap: C - frac * C, off: -offset * C };
          offset += frac;
          return seg;
        })
      : [];
  return (
    <div className="flex items-center gap-1">
      <div className="relative h-[104px] w-[104px] shrink-0">
        <svg viewBox="0 0 104 104" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="52"
            cy="52"
            r={R}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="9"
          />
          {arcs.map((a) => (
            <circle
              key={a.label}
              cx="52"
              cy="52"
              r={R}
              fill="none"
              stroke={a.color}
              strokeWidth="9"
              strokeDasharray={`${a.dash} ${a.gap}`}
              strokeDashoffset={a.off}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
          <span className="max-w-[48px] truncate text-lg font-semibold leading-none tabular-nums">
            {total}
          </span>
          <span className="line-clamp-2 max-w-[56px] break-words text-center text-[0.55rem] uppercase leading-tight text-[var(--muted-foreground)]">
            {tq("judge.casDisagree")}
          </span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-1">
        {data.length === 0 ? (
          <li className="text-[0.7rem] text-[var(--muted-foreground)]">
            {tq("judge.noDisagreements")}
          </li>
        ) : (
          data.map((d) => (
            <li key={d.label} className="flex flex-col gap-0.5 text-[0.66rem]">
              <span className="flex min-w-0 items-center gap-1">
                <span className="h-1 w-1 shrink-0 rounded-full" style={{ background: d.color }} />
                <span className="min-w-0 truncate">{tq(`judge.cat.${d.label}`)}</span>
              </span>
              <span className="pl-2.5 tabular-nums text-[var(--muted-foreground)]">
                {d.count} · {total > 0 ? Math.round((d.count / total) * 100) : 0}%
              </span>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}

/** Per-slice agreement rows (language / metric) with a mini agreement bar. */
function GroupRows({
  groups,
  labelKey,
  showKappa = false,
}: {
  groups: GroupAgreement[];
  labelKey?: (label: string) => string;
  showKappa?: boolean;
}) {
  return (
    <ul className="flex flex-col gap-1.5">
      {groups.map((g) => {
        const tone = g.agreement >= 0.95 ? MATCH : g.agreement >= 0.8 ? "#f59e0b" : MISS;
        return (
          <li key={g.label} className="flex items-center gap-2 text-[0.72rem]">
            <span className="w-24 shrink-0 truncate">{labelKey ? labelKey(g.label) : g.label}</span>
            <div className="h-[4px] flex-1 overflow-hidden rounded-sm bg-[var(--tessera-border)]">
              <div
                className="h-full rounded-sm"
                style={{ width: `${g.agreement * 100}%`, background: tone }}
              />
            </div>
            <span className="w-9 shrink-0 text-right tabular-nums" style={{ color: tone }}>
              {Math.round(g.agreement * 100)}%
            </span>
            {showKappa ? (
              <span className="w-12 shrink-0 text-right tabular-nums text-[var(--muted-foreground)]">
                κ {g.kappa.toFixed(2)}
              </span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}

/** Small line of judge-metric drift buckets — the κ-evolution stability proxy. */
function MiniLine({ buckets, baseline }: { buckets: SeriesBucket[]; baseline?: number }) {
  const pts = buckets.filter((b) => b.mean != null).map((b) => b.mean as number);
  if (pts.length < 2)
    return <p className="py-6 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>;
  const W = 200;
  const H = 56;
  const min = Math.min(...pts, baseline ?? 1);
  const max = Math.max(...pts, baseline ?? 0);
  const span = max - min || 1;
  const x = (i: number) => (i / (pts.length - 1)) * W;
  const y = (v: number) => H - 4 - ((v - min) / span) * (H - 8);
  const line = pts
    .map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-14 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {baseline != null ? (
        <line
          x1={0}
          x2={W}
          y1={y(baseline)}
          y2={y(baseline)}
          stroke="var(--muted-foreground)"
          strokeWidth="0.6"
          strokeDasharray="3 3"
        />
      ) : null}
      <path d={line} fill="none" stroke="#a78bfa" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

/** A governed recommended-action card (zone D), faithful to image 05. */
function ActionCard({
  n,
  title,
  desc,
  roles,
  cta,
  ctaTone = "outline",
}: {
  n: number;
  title: string;
  desc: string;
  roles: { label: string; tone: "warning" | "success" | "neutral" | "danger" }[];
  cta: string;
  ctaTone?: "outline" | "danger";
}) {
  return (
    <Card className="flex min-w-0 flex-col gap-2 p-3">
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-muted)] text-[0.6rem] font-semibold tabular-nums">
          {n}
        </span>
        <span className="min-w-0 text-[0.78rem] font-medium leading-snug">{title}</span>
      </div>
      <p className="text-[0.68rem] leading-snug text-[var(--muted-foreground)]">{desc}</p>
      <div className="flex flex-wrap gap-1">
        {roles.map((r) => (
          <Badge key={r.label} tone={r.tone}>
            {r.label}
          </Badge>
        ))}
      </div>
      <Button
        size="sm"
        variant="outline"
        className={`mt-auto h-7 justify-center text-[0.7rem] ${
          ctaTone === "danger"
            ? "border-[#b45309] bg-[#78350f]/40 text-amber-200 hover:bg-[#78350f]/60"
            : ""
        }`}
      >
        {cta}
      </Button>
    </Card>
  );
}

// ── main hero (zones A · B · C · D) ──────────────────────────────────────────

/** Full judge-calibration hero, faithful to the normative tab (image 05):
 * A. État actuel · B. Diagnostic de calibration · C. Segments à risque & dérive ·
 * D. Actions recommandées. Everything is real: the gold-set points (scored by the
 * sovereign llama3.2:3b judge, backfilled to eval/calibration/_calibration.json)
 * feed the matrix/curve/distribution and the per-language/-metric/-segment
 * breakdowns; `drift` is the durable judge-score drift over the window. */
export function JudgeCalibration({
  data,
  drift,
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
  const tp = points.filter((p) => p.judge_label === "good" && p.human_label === "good").length;
  const tn = points.filter((p) => p.judge_label !== "good" && p.human_label !== "good").length;
  const fp =
    data.fp ?? points.filter((p) => p.judge_label === "good" && p.human_label !== "good").length;
  const fn =
    data.fn ?? points.filter((p) => p.judge_label !== "good" && p.human_label === "good").length;
  const kappa = data.kappa ?? 0;
  const verbosity = data.verbosity_corr ?? 0;
  const clemency = data.mean_score_bad ?? 0;
  const nDisagree = data.n_disagree ?? points.filter((p) => !p.match).length;
  const driftDiv = drift?.divergence ?? null;

  const kappaTone = kappa >= 0.8 ? GOOD : kappa >= 0.6 ? WARN : BAD;
  const verbTone = Math.abs(verbosity) < 0.2 ? GOOD : Math.abs(verbosity) < 0.4 ? WARN : BAD;

  const donutData = Object.entries(data.disagreement_by_category ?? {})
    .map(([label, count]) => ({ label, count, color: catColor(label) }))
    .sort((a, b) => b.count - a.count);

  const disagreements = points.filter((p) => !p.match);
  const overrides = points.filter((p) => p.human_override);

  return (
    <div className="flex flex-col gap-2">
      {/* A. État actuel ── KPI strip (8 tiles) */}
      <Sec>{tq("judge.secActual")}</Sec>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        <Kpi
          label={tq("judge.kappaTitle")}
          explainKey="jgKappa"
          value={kappa.toFixed(2)}
          tone={kappaTone}
          hint={tq("judge.vsBaseline")}
        />
        <Kpi
          label={tq("judge.agreementGlobal")}
          explainKey="jgAgreement"
          value={data.agreement == null ? "—" : `${Math.round(data.agreement * 100)}%`}
          tone={data.agreement != null && data.agreement >= 0.8 ? GOOD : WARN}
          hint={tq("judge.vsBaseline")}
        />
        <Kpi
          label={tq("judge.fp")}
          explainKey="jgFp"
          value={`${((fp / total) * 100).toFixed(1)}%`}
          tone={fp / total < 0.05 ? GOOD : WARN}
          hint={`${fp}/${total}`}
        />
        <Kpi
          label={tq("judge.fn")}
          explainKey="jgFn"
          value={`${((fn / total) * 100).toFixed(1)}%`}
          tone={fn / total < 0.05 ? GOOD : WARN}
          hint={`${fn}/${total}`}
        />
        <Kpi
          label={tq("judge.verbosityBias")}
          explainKey="jgVerbosity"
          value={verbosity.toFixed(2)}
          tone={verbTone}
          hint={tq("judge.vsBaseline")}
        />
        <Kpi
          label={tq("judge.clemency")}
          explainKey="jgClemency"
          value={clemency.toFixed(2)}
          tone={clemency < 0.2 ? GOOD : clemency < 0.4 ? WARN : BAD}
          hint={tq("judge.vsBaseline")}
        />
        <Kpi
          label={tq("judge.drift")}
          explainKey="jgDrift"
          value={driftDiv == null ? "—" : driftDiv.toFixed(2)}
          tone={driftDiv == null ? MUTED : driftDiv < 0.05 ? GOOD : driftDiv < 0.1 ? WARN : BAD}
          hint={tq("judge.vsBaseline")}
        />
        <Kpi
          label={tq("judge.casDisagree")}
          explainKey="jgDisagree"
          value={`${nDisagree}`}
          tone={nDisagree === 0 ? GOOD : WARN}
          hint={`${tq("judge.overrides")}: ${data.n_overrides ?? 0}`}
        />
      </div>

      {/* B. Diagnostic de calibration ── matrix · curve · distribution · donut */}
      <Sec>{tq("judge.secDiag")}</Sec>
      <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-4">
        <Panel title={`1) ${tq("judge.confusion")}`} explainKey="jgConfusion">
          <ConfusionMatrix tp={tp} fp={fp} fn={fn} tn={tn} />
        </Panel>
        <Panel title={`2) ${tq("judge.curve")}`} explainKey="jgCurve">
          <CalibrationCurve points={points} />
        </Panel>
        <Panel title={`3) ${tq("judge.distribution")}`} explainKey="jgDistribution">
          <ScoreDistribution points={points} />
        </Panel>
        <Panel title={`4) ${tq("judge.disagreeDist")}`} explainKey="jgDisagreeDist">
          <DisagreementDonut data={donutData} total={nDisagree} />
        </Panel>
      </div>

      {/* C. Segments à risque & dérive */}
      <Sec>{tq("judge.secSegments")}</Sec>
      <div className="grid items-start gap-2 lg:grid-cols-2 2xl:grid-cols-4">
        <Panel
          title={`1) ${tq("judge.kappaEvolution")}`}
          explainKey="jgKappaEvo"
          className="2xl:col-span-1"
        >
          <MiniLine buckets={drift?.buckets ?? []} baseline={drift?.mean ?? undefined} />
          <p className="mt-1 text-[0.62rem] text-[var(--muted-foreground)]">
            {tq("judge.kappaEvolutionNote")}
          </p>
        </Panel>
        <Panel title={`2) ${tq("judge.byLanguage")}`} explainKey="jgByLang">
          <GroupRows groups={data.by_language ?? []} labelKey={(l) => l.toUpperCase()} showKappa />
        </Panel>
        <Panel title={`3) ${tq("judge.byMetric")}`} explainKey="jgByMetric">
          <GroupRows groups={data.by_category ?? []} labelKey={(l) => tq(`judge.cat.${l}`)} />
        </Panel>
        <div className="flex flex-col gap-2">
          <Panel title={`4) ${tq("judge.topSegments")}`} explainKey="jgTopSeg">
            <ul className="flex flex-col gap-1 text-[0.72rem]">
              {(data.by_segment ?? [])
                .filter((s) => s.n_disagree > 0)
                .slice(0, 4)
                .map((s) => (
                  <li key={s.label} className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate">{s.label}</span>
                    <Badge tone="warning">
                      {s.n_disagree}/{s.n}
                    </Badge>
                  </li>
                ))}
              {(data.by_segment ?? []).every((s) => s.n_disagree === 0) ? (
                <li className="text-[var(--muted-foreground)]">{tq("judge.noDisagreements")}</li>
              ) : null}
            </ul>
          </Panel>
          <Panel title={`5) ${tq("judge.overrides")}`} explainKey="jgOverrides">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold tabular-nums">{data.n_overrides ?? 0}</span>
              <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                {total > 0 ? `${(((data.n_overrides ?? 0) / total) * 100).toFixed(1)}%` : "—"}
              </span>
            </div>
            <ul className="mt-1 flex flex-col gap-0.5">
              {overrides.slice(0, 3).map((o) => (
                <li
                  key={o.case_id}
                  className="truncate font-mono text-[0.62rem] text-[var(--muted-foreground)]"
                >
                  {o.case_id}
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>

      {/* 6) Cas échoués représentatifs */}
      <Panel title={`6) ${tq("judge.repCases")}`} explainKey="jgRepCases">
        {disagreements.length === 0 ? (
          <p className="py-3 text-center text-sm text-[var(--muted-foreground)]">
            {tq("judge.noDisagreements")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-3 font-medium">{tq("judge.cols.id")}</th>
                  <th className="py-2 pr-3 font-medium">{tq("judge.cols.statement")}</th>
                  <th className="py-2 pr-3 font-medium">{tq("judge.cols.category")}</th>
                  <th className="py-2 pr-3 font-medium">{tq("judge.cols.judgeScore")}</th>
                  <th className="py-2 pr-3 font-medium">{tq("judge.cols.humanAgree")}</th>
                  <th className="py-2 font-medium">{tq("judge.cols.status")}</th>
                </tr>
              </thead>
              <tbody>
                {disagreements.map((p) => (
                  <tr key={p.case_id || p.question} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-3 font-mono text-[0.7rem]">{p.case_id || "—"}</td>
                    <td className="py-2 pr-3 text-[var(--muted-foreground)]">
                      <span className="line-clamp-1 max-w-sm">{p.question}</span>
                    </td>
                    <td className="py-2 pr-3">
                      <span className="inline-flex items-center gap-1">
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: catColor(p.category ?? "") }}
                        />
                        {tq(`judge.cat.${p.category}`)}
                      </span>
                    </td>
                    <td className="py-2 pr-3 tabular-nums">{p.judge_score.toFixed(2)}</td>
                    <td className="py-2 pr-3">
                      <Badge tone="danger">{tq("judge.disagree")}</Badge>
                    </td>
                    <td className="py-2">
                      <Badge tone="warning">{tq("judge.status.review")}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* D. Actions recommandées ── 6 governed cards */}
      <Sec>{tq("judge.secActions")}</Sec>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        <ActionCard
          n={1}
          title={tq("judge.act.recalTitle")}
          desc={tq("judge.act.recalDesc")}
          roles={[{ label: "Operator+", tone: "success" }]}
          cta={tq("judge.act.recalCta")}
        />
        <ActionCard
          n={2}
          title={tq("judge.act.curateTitle", { n: nDisagree })}
          desc={tq("judge.act.curateDesc")}
          roles={[{ label: "Admin+", tone: "warning" }]}
          cta={tq("judge.act.curateCta")}
        />
        <ActionCard
          n={3}
          title={tq("judge.act.shadowTitle")}
          desc={tq("judge.act.shadowDesc")}
          roles={[{ label: "Operator+", tone: "success" }]}
          cta={tq("judge.act.shadowCta")}
        />
        <ActionCard
          n={4}
          title={tq("judge.act.freezeTitle")}
          desc={tq("judge.act.freezeDesc")}
          roles={[
            { label: "Admin+", tone: "warning" },
            { label: "Dual control", tone: "danger" },
          ]}
          cta={tq("judge.act.freezeCta")}
          ctaTone="danger"
        />
        <ActionCard
          n={5}
          title={tq("judge.act.complianceTitle")}
          desc={tq("judge.act.complianceDesc")}
          roles={[{ label: "Compliance+", tone: "neutral" }]}
          cta={tq("judge.act.complianceCta")}
        />
        <ActionCard
          n={6}
          title={tq("judge.act.evidenceTitle")}
          desc={tq("judge.act.evidenceDesc")}
          roles={[{ label: "Auditor+", tone: "neutral" }]}
          cta={tq("judge.act.evidenceCta")}
        />
      </div>

      {/* Footer chips */}
      <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--muted-foreground)]">
        <Chip
          icon={Boxes}
          label={`${tq("judge.chip.dataset")}: judge-gold-v1`}
          tone="text-[var(--tessera-green)]"
        />
        <Chip
          icon={CalendarClock}
          label={`${tq("judge.chip.judge")}: ${data.judge_model ?? "—"}`}
        />
        <Chip icon={Landmark} label={tq("judge.chip.truth")} />
        <Chip
          icon={ShieldCheck}
          label={tq("judge.chip.chain")}
          tone="text-[var(--tessera-green)]"
        />
      </div>
    </div>
  );
}

/** A bordered, titled mini-card used across zones B/C. */
function Panel({
  title,
  explainKey,
  children,
  className,
}: {
  title: string;
  explainKey?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={`min-w-0 ${className ?? ""}`}>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-[0.78rem] font-medium">
          {title}
          {explainKey ? <QInfo title={title} k={explainKey} /> : null}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
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

// ── dedicated right rail (JudgeRail) ─────────────────────────────────────────

/** The Calibration-juge right rail (image 05): judge fiche · quality gates ·
 * risk summary · top disagreement categories · recent activity · sensitive
 * actions · evidence pack. Driven by the real calibration + drift signals. */
export function JudgeRail({
  data,
  drift,
  release,
  onEvidence,
}: {
  data: Calibration | undefined;
  drift?: JudgeDrift;
  release?: ReleaseStatus | undefined;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const kappa = data?.kappa ?? null;
  const agreement = data?.agreement ?? null;
  const driftDiv = drift?.divergence ?? null;
  const nDisagree = data?.n_disagree ?? 0;

  // Transparent 0-100 composite of the real signals (1−κ, drift, 1−agreement).
  const factors: number[] = [];
  if (kappa != null) factors.push(Math.max(0, 1 - kappa));
  if (driftDiv != null) factors.push(Math.min(1, driftDiv / 0.1));
  if (agreement != null) factors.push(Math.max(0, 1 - agreement));
  const risk = factors.length
    ? Math.round((factors.reduce((s, f) => s + f, 0) / factors.length) * 100)
    : 0;
  const riskTone = risk >= 50 ? BAD : risk >= 25 ? WARN : GOOD;
  const riskLevel =
    risk >= 50 ? tq("judge.riskHigh") : risk >= 25 ? tq("judge.riskMod") : tq("judge.riskLow");

  const gates: { label: string; value: string; pass: boolean }[] = [
    {
      label: tq("judge.gateCalibration"),
      value: kappa == null ? "—" : kappa.toFixed(2),
      pass: (kappa ?? 0) >= 0.8,
    },
    {
      label: tq("judge.gateAgreement"),
      value: agreement == null ? "—" : `${Math.round(agreement * 100)}%`,
      pass: (agreement ?? 0) >= 0.8,
    },
    {
      label: tq("judge.gateDrift"),
      value: driftDiv == null ? "—" : driftDiv.toFixed(2),
      pass: (driftDiv ?? 0) < 0.1,
    },
  ];

  const topCats = Object.entries(data?.disagreement_by_category ?? {})
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count);
  const maxCat = Math.max(1, ...topCats.map((c) => c.count));

  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-28">
        {/* Fiche juge */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("judge.fiche")}
              <QInfo title={tq("judge.fiche")} k="jgFiche" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 text-[0.72rem]">
            <RailRow label={tq("judge.model")}>
              <span className="font-mono text-[0.7rem]">{data?.judge_model ?? "—"}</span>
            </RailRow>
            <RailRow label={tq("judge.byHumans")}>
              <span className="tabular-nums">{data?.n ?? "—"}</span>
            </RailRow>
            {release?.current ? (
              <RailRow label={tq("rr.release")}>
                <span className="tabular-nums">{release.current.version}</span>
              </RailRow>
            ) : null}
          </CardContent>
        </Card>

        {/* Gates qualité */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("judge.qualityGates")}
              <QInfo title={tq("judge.qualityGates")} k="jgGates" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {gates.map((g) => (
              <div key={g.label} className="flex items-center justify-between gap-2 text-[0.72rem]">
                <span className="min-w-0 truncate text-[var(--muted-foreground)]">{g.label}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className="tabular-nums">{g.value}</span>
                  <Badge tone={g.pass ? "success" : "warning"}>
                    {g.pass ? tq("judge.pass") : tq("judge.watch")}
                  </Badge>
                </span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Résumé du risque */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("judge.riskSummary")}
              <QInfo title={tq("judge.riskSummary")} k="jgRisk" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <div className="flex items-end gap-2">
              <span className={`text-3xl font-semibold tabular-nums ${riskTone}`}>{risk}</span>
              <span className="pb-1 text-xs text-[var(--muted-foreground)]">/100</span>
              <span className={`pb-1 text-xs ${riskTone}`}>· {riskLevel}</span>
            </div>
            <ul className="flex flex-col gap-1 text-[0.68rem] text-[var(--muted-foreground)]">
              <li>• {tq("judge.attnOverconfidence")}</li>
              <li>• {tq("judge.attnRegCases")}</li>
              <li>• {tq("judge.attnDe")}</li>
            </ul>
          </CardContent>
        </Card>

        {/* Top catégories en désaccord */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("judge.topDisagree")}
              <QInfo title={tq("judge.topDisagree")} k="jgTopDisagree" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {topCats.length === 0 ? (
              <p className="text-[0.7rem] text-[var(--muted-foreground)]">
                {tq("judge.noDisagreements")}
              </p>
            ) : (
              topCats.map((c) => (
                <div key={c.label} className="flex items-center gap-2 text-[0.72rem]">
                  <span className="w-20 shrink-0 truncate">{tq(`judge.cat.${c.label}`)}</span>
                  <div className="h-[4px] flex-1 overflow-hidden rounded-sm bg-[var(--tessera-border)]">
                    <div
                      className="h-full rounded-sm"
                      style={{
                        width: `${(c.count / maxCat) * 100}%`,
                        background: catColor(c.label),
                      }}
                    />
                  </div>
                  <span className="w-12 shrink-0 text-right tabular-nums text-[var(--muted-foreground)]">
                    {c.count} · {nDisagree > 0 ? Math.round((c.count / nDisagree) * 100) : 0}%
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Actions sensibles */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {tq("judge.sensitiveActions")}
              <QInfo title={tq("judge.sensitiveActions")} k="jgSensitive" />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <SensitiveAction icon={Snowflake} label={tq("judge.act.freezeTitle")} />
            <SensitiveAction icon={RefreshCw} label={tq("judge.changeThresholds")} />
          </CardContent>
        </Card>

        {/* Evidence pack */}
        <button
          type="button"
          onClick={onEvidence}
          className="flex items-center gap-3 rounded-lg border border-[#5b4bbd] bg-gradient-to-br from-[#4c3fb0]/40 to-[#3a2f8a]/30 px-3 py-3 text-left transition-colors hover:from-[#4c3fb0]/60"
        >
          <GitCompareArrows className="h-5 w-5 shrink-0 text-[#c4b5fd]" />
          <span className="flex min-w-0 flex-col">
            <span className="text-[0.8rem] font-medium">{tq("judge.evidencePack")}</span>
            <span className="text-[0.65rem] text-[var(--muted-foreground)]">
              {tq("judge.evidencePackHint")}
            </span>
          </span>
        </button>
      </div>
    </aside>
  );
}

function RailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--muted-foreground)]">{label}</span>
      {children}
    </div>
  );
}

function SensitiveAction({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2 py-1.5 text-[0.72rem]">
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <Badge tone="warning">Admin+</Badge>
      <Badge tone="danger">Dual</Badge>
    </div>
  );
}

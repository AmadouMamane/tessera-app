"use client";

import { ArrowUpRight, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricKpi } from "@/components/observability/evolution-chart";
import type { SignalRow } from "@/components/observability/signals-table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Truncate } from "@/components/ui/truncate";
import type {
  IntentReport,
  JudgeDrift,
  LocalizationReport,
  MetricPairs,
  PredictorEvaluation,
  RegressionRisk,
  ScoreSeries,
} from "@/lib/api/schemas";
import { useDecimalFormat, usePercentFormat } from "@/lib/format-number";

/** Overview drill-down targets. Four of them live on the evaluations view (`CROSSED_TARGETS`). */
export type OverviewTab = "overview" | "signals" | "runs" | "failed" | "models" | "judge";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";
const MUTED = "text-[var(--muted-foreground)]";

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

/**
 * The headline KPI strip of the Vue d'ensemble — production reads only.
 *
 * It used to hold eight tiles, four of which (non-regression rate, open regressions, judge
 * agreement on the gold set, evaluated case count) summarised the EVAL ARCHIVE — the other
 * view's question, answered louder here than there. Those tiles live on the evaluations view
 * now; what remains is what this view samples: the SLO, the three judged production series,
 * and how many registry signals are breaching right now.
 */
export function OverviewKpis({
  sloPct,
  faithfulness,
  grounding,
  hallucination,
  signalsCrit,
  loading,
  onOpen,
}: {
  sloPct: number | null;
  faithfulness: ScoreSeries | undefined;
  grounding: ScoreSeries | undefined;
  hallucination: ScoreSeries | undefined;
  /** Registry rows above their critical bar — a count of the screen's own rows, never a guess. */
  signalsCrit: number | null;
  loading: boolean;
  /** Makes each KPI tile drill into its detail tab (↗). */
  onOpen?: (tab: OverviewTab) => void;
}) {
  const tq = useTranslations("quality");
  const scoreTone = sloPct == null ? MUTED : sloPct >= 80 ? GOOD : sloPct >= 60 ? WARN : BAD;
  const critTone = signalsCrit == null ? MUTED : signalsCrit === 0 ? GOOD : BAD;
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-3 2xl:grid-cols-5">
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
      <MetricKpi
        label={tq("metrics.hallucination")}
        series={hallucination}
        loading={loading}
        info={<KpiInfo title={tq("metrics.hallucination")} k="hallucination" />}
        onDrill={onOpen ? () => onOpen("signals") : undefined}
        drillLabel={tq("seeDetail")}
      />
      <ValueKpi
        label={tq("exec.kpi.signalsCrit")}
        value={signalsCrit == null ? "—" : String(signalsCrit)}
        tone={critTone}
        info={<KpiInfo title={tq("exec.kpi.signalsCrit")} k="signalsCrit" />}
        onDrill={onOpen ? () => onOpen("signals") : undefined}
        drillLabel={tq("seeDetail")}
      />
    </div>
  );
}

/** "État actuel" — narrow status column: global score, failing/alert counts and the
 * period-over-period evolution. The release rows it used to carry (impact, version, blocked
 * badge) belong to the evaluations view and left with the rest of the eval-shaped overview. */
export function EtatActuel({
  summary,
  evolutionDelta,
  scorePct,
  series,
}: {
  summary: { ok: number; warn: number; crit: number; na: number; total: number };
  evolutionDelta: number | null;
  scorePct: number | null;
  series: ScoreSeries | undefined;
}) {
  const tq = useTranslations("quality");
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

/**
 * The failing/at-risk registry signals, worst first — the overview's second read.
 *
 * Headerless on purpose: it sits inside a labelled zone band, which already names it. Each row
 * drills into the registry with the signal focused — a breach the reader cannot open is a
 * decoration.
 */
export function TopProblems({
  rows,
  limit = 6,
  onSelect,
}: {
  rows: SignalRow[];
  limit?: number;
  /** Focus this signal in the registry (switch tab + `?signal=`). */
  onSelect?: (row: SignalRow) => void;
}) {
  const tq = useTranslations("quality");
  const problems = rows
    .filter((r) => r.status === "crit" || r.status === "warn")
    .sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9))
    .slice(0, limit);
  return (
    <Card>
      <CardContent className="pt-3">
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
                  <tr
                    key={r.key}
                    className={`border-b border-[var(--border)]/50 ${
                      onSelect
                        ? "cursor-pointer transition-colors hover:bg-[var(--tessera-muted)]/60"
                        : ""
                    }`}
                    onClick={onSelect ? () => onSelect(r) : undefined}
                  >
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
  const dec2 = useDecimalFormat(2);
  const pctFmt = usePercentFormat(1);
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
                  {riskScore == null ? "—" : `${dec2(riskScore)}/1`}
                </span>
              </Row>
              <Row label={tq("pred.drift")}>
                <span className="flex items-center gap-1.5">
                  <span className="tabular-nums">{pctFmt(div)}</span>
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
                {/* An unmeasured localization report is NOT a complete one. The endpoint
                    reported 100 % in production for its whole life because it could not open
                    the catalogues and divided by an empty reference; the row must not turn
                    that back into a reassuring dash. */}
                {localization && (!localization.available || localization.measured === false) ? (
                  <span className={`text-xs ${WARN}`}>{tq("pred.langsUnmeasured")}</span>
                ) : langs.length === 0 ? (
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

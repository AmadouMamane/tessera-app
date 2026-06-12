"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, BadgeCheck, Gauge, Languages, Quote, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { ObservabilityDashboard } from "@/components/observability/observability-dashboard";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchCalibration,
  fetchCitations,
  fetchConformance,
  fetchEvalScores,
  fetchFunnel,
  fetchIntent,
  fetchLocaleFormat,
  fetchRefusal,
  fetchRoadmap,
  fetchRouting,
  fetchSLO,
  fetchTrend,
} from "@/lib/api/client";
import { cn } from "@/lib/cn";
import {
  type OverviewTone,
  controlState,
  dotBg,
  pct,
  rateTone,
  score100,
  toneBg,
  toneText,
} from "@/lib/overview";

const POLL_MS = 15_000;

// Palette for the categorical donuts (languages / intents).
const SLICE = ["#3ba0ff", "#37d39b", "#f0a23a", "#b98bff", "#ff6f91", "#5fd0d8", "#c7d04a"];
const sliceColor = (i: number): string => SLICE[i % SLICE.length] ?? "#3ba0ff";

export function QualityDashboard() {
  const t = useTranslations("quality");
  const [tab, setTab] = useState<"dashboard" | "signals">("dashboard");

  return (
    <div className="flex w-full flex-col gap-4 pb-8">
      <nav className="flex flex-wrap items-center gap-1 border-b border-[var(--border)] pb-px">
        <TabButton active={tab === "dashboard"} onClick={() => setTab("dashboard")}>
          {t("tabs.dashboard")}
        </TabButton>
        <TabButton active={tab === "signals"} onClick={() => setTab("signals")}>
          {t("tabs.signals")}
        </TabButton>
      </nav>
      {tab === "dashboard" ? <ExecutiveView /> : <ObservabilityDashboard />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "-mb-px rounded-t-md border-b-2 px-4 py-2 text-sm transition-colors",
        active
          ? "border-gold-400 font-semibold text-[var(--foreground)]"
          : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Executive quality view
// ---------------------------------------------------------------------------

function ExecutiveView() {
  const t = useTranslations("quality");

  const slo = useQuery({
    queryKey: ["q-slo"],
    queryFn: ({ signal }) => fetchSLO(signal),
    refetchInterval: POLL_MS,
  });
  const trend = useQuery({
    queryKey: ["q-trend"],
    queryFn: ({ signal }) => fetchTrend(signal),
    refetchInterval: POLL_MS,
  });
  const scores = useQuery({
    queryKey: ["q-scores"],
    queryFn: ({ signal }) => fetchEvalScores(signal),
    refetchInterval: POLL_MS,
  });
  const calibration = useQuery({
    queryKey: ["q-calibration"],
    queryFn: ({ signal }) => fetchCalibration(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const citations = useQuery({
    queryKey: ["q-citations"],
    queryFn: ({ signal }) => fetchCitations(signal),
    refetchInterval: POLL_MS,
  });
  const locale = useQuery({
    queryKey: ["q-locale"],
    queryFn: ({ signal }) => fetchLocaleFormat(signal),
    refetchInterval: POLL_MS,
  });
  const refusal = useQuery({
    queryKey: ["q-refusal"],
    queryFn: ({ signal }) => fetchRefusal(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const conformance = useQuery({
    queryKey: ["q-conformance"],
    queryFn: ({ signal }) => fetchConformance(signal),
    refetchInterval: POLL_MS,
  });
  const routing = useQuery({
    queryKey: ["q-routing"],
    queryFn: ({ signal }) => fetchRouting(signal),
    refetchInterval: POLL_MS,
  });
  const intent = useQuery({
    queryKey: ["q-intent"],
    queryFn: ({ signal }) => fetchIntent(signal),
    refetchInterval: POLL_MS,
  });
  const funnel = useQuery({
    queryKey: ["q-funnel"],
    queryFn: ({ signal }) => fetchFunnel(signal),
    refetchInterval: POLL_MS,
  });
  const roadmap = useQuery({
    queryKey: ["q-roadmap"],
    queryFn: ({ signal }) => fetchRoadmap(signal),
    refetchInterval: 30_000,
  });

  const sparkline = trend.data?.buckets.map((b) => b.mean);

  // The quality dimensions: each a 0..1 "higher is better" score from a real
  // signal. Rows with no data yet are dropped (honest empty state).
  const dims: DimRow[] = [];
  if (slo.data && slo.data.n > 0)
    dims.push(dim("fidelity", slo.data.good_rate, slo.data.target, sparkline));
  if (citations.data && citations.data.n_citations > 0)
    dims.push(dim("citations", citations.data.validity_rate, 0.95));
  if (locale.data && locale.data.n_amounts > 0)
    dims.push(dim("locale", locale.data.correctness_rate, 0.95));
  if (refusal.data && refusal.data.n_legit + refusal.data.n_forbidden > 0)
    dims.push(
      dim(
        "refusal",
        1 - Math.max(refusal.data.over_refusal_rate, refusal.data.under_refusal_rate),
        0.95,
      ),
    );
  if (conformance.data && conformance.data.n_calls > 0)
    dims.push(dim("conformance", conformance.data.conformance_rate, 0.95));
  if (routing.data && routing.data.n > 0)
    dims.push(dim("routing", 1 - routing.data.mismatch_rate, 0.95));

  const langSlices = (funnel.data?.languages ?? []).map((l, i) => ({
    label: l.language.toUpperCase(),
    value: l.n_turns,
    color: sliceColor(i),
  }));
  const intentSlices = Object.entries(intent.data?.distribution ?? {})
    .sort((a, b) => b[1] - a[1])
    .map(([label, value], i) => ({ label, value, color: sliceColor(i) }));

  const kappa = calibration.data?.available ? calibration.data.kappa : null;

  return (
    <>
      {/* KPI row */}
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
        <Kpi
          icon={Gauge}
          label={t("kpi.quality")}
          value={slo.data && slo.data.n > 0 ? score100(slo.data.good_rate) : "—"}
          sub={slo.data ? t("kpi.qualitySub", { n: slo.data.n }) : ""}
          tone={slo.data && slo.data.n > 0 ? rateTone(slo.data.good_rate) : "neutral"}
          loading={slo.isLoading}
        />
        <Kpi
          icon={Activity}
          label={t("kpi.evals")}
          value={scores.data ? String(scores.data.scores.length) : "—"}
          sub={t("kpi.evalsSub")}
          tone="info"
          loading={scores.isLoading}
        />
        <Kpi
          icon={Quote}
          label={t("kpi.citations")}
          value={
            citations.data && citations.data.n_citations > 0
              ? pct(citations.data.validity_rate)
              : "—"
          }
          sub={citations.data ? t("kpi.citationsSub", { n: citations.data.n_unsupported }) : ""}
          tone={
            citations.data && citations.data.n_citations > 0
              ? rateTone(citations.data.validity_rate)
              : "neutral"
          }
          loading={citations.isLoading}
        />
        <Kpi
          icon={Languages}
          label={t("kpi.locale")}
          value={locale.data && locale.data.n_amounts > 0 ? pct(locale.data.correctness_rate) : "—"}
          sub={locale.data ? t("kpi.localeSub", { n: locale.data.n_violations }) : ""}
          tone={
            locale.data && locale.data.n_amounts > 0
              ? rateTone(locale.data.correctness_rate)
              : "neutral"
          }
          loading={locale.isLoading}
        />
        <Kpi
          icon={ShieldCheck}
          label={t("kpi.conformance")}
          value={
            conformance.data && conformance.data.n_calls > 0
              ? pct(conformance.data.conformance_rate)
              : "—"
          }
          sub={conformance.data ? t("kpi.conformanceSub", { n: conformance.data.n_calls }) : ""}
          tone={
            conformance.data && conformance.data.n_calls > 0
              ? rateTone(conformance.data.conformance_rate)
              : "neutral"
          }
          loading={conformance.isLoading}
        />
        <Kpi
          icon={BadgeCheck}
          label={t("kpi.calibration")}
          value={kappa != null ? kappa.toFixed(2) : "—"}
          sub={kappa != null ? t("kpi.calibrationSub") : t("kpi.calibrationNa")}
          tone={
            kappa == null
              ? "neutral"
              : kappa >= 0.6
                ? "success"
                : kappa >= 0.4
                  ? "warning"
                  : "danger"
          }
          loading={calibration.isLoading}
        />
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-4">
          <PerformanceTable dims={dims} loading={slo.isLoading && dims.length === 0} />
          <ScoreEvolution trend={trend.data} />
          <div className="grid gap-4 sm:grid-cols-2">
            <DonutCard
              title={t("languages.title")}
              slices={langSlices}
              loading={funnel.isLoading}
            />
            <DonutCard
              title={t("intents.title")}
              slices={intentSlices}
              loading={intent.isLoading}
            />
          </div>
        </div>
        <aside className="flex min-w-0 flex-col gap-4">
          <RadarCard dims={dims} />
          <DiagnosticCard
            items={roadmap.data?.items ?? []}
            loading={roadmap.isLoading}
            n={roadmap.data?.n_items ?? 0}
          />
          <ActivityCard scores={scores.data?.scores} loading={scores.isLoading} />
        </aside>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Dimensions model
// ---------------------------------------------------------------------------

interface DimRow {
  id: string; // i18n key under quality.signals
  value: number; // 0..1, higher = better
  target: number;
  tone: OverviewTone;
  stateKey: "ok" | "warn" | "fail";
  trend?: number[];
}

function dim(id: string, value: number, target: number, trend?: number[]): DimRow {
  const st = controlState(value, target, "higher");
  return { id, value, target, tone: st.tone, stateKey: st.key, trend };
}

// ---------------------------------------------------------------------------
// KPI card
// ---------------------------------------------------------------------------

function Kpi({
  icon: Icon,
  label,
  value,
  sub,
  tone,
  loading,
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  sub: string;
  tone: OverviewTone;
  loading?: boolean;
}) {
  return (
    <Card className="relative overflow-hidden rounded-lg">
      <div className={cn("absolute inset-x-0 top-0 h-0.5", dotBg[tone])} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <p className="text-xs text-[var(--muted-foreground)]">{label}</p>
          <span className={cn("rounded-lg border p-1.5", toneBg[tone])}>
            <Icon className="h-4 w-4" />
          </span>
        </div>
        {loading ? (
          <Skeleton className="mt-2 h-7 w-16" />
        ) : (
          <p className="mt-2 font-serif text-2xl font-semibold tabular-nums">{value}</p>
        )}
        {sub ? <p className={cn("mt-1 text-[0.7rem]", toneText[tone])}>{sub}</p> : null}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Performance par signal
// ---------------------------------------------------------------------------

function PerformanceTable({ dims, loading }: { dims: DimRow[]; loading: boolean }) {
  const t = useTranslations("quality");
  const ts = useTranslations("quality.signals");
  const tst = useTranslations("quality.states");
  return (
    <Card className="overflow-hidden rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm">{t("perf.title")}</CardTitle>
        <span className="text-xs text-[var(--muted-foreground)]">
          {t("perf.count", { n: dims.length })}
        </span>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="flex flex-col gap-2 p-4">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        ) : dims.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-[var(--muted-foreground)]">
            {t("empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="px-4 py-2 font-medium">{t("perf.signal")}</th>
                  <th className="py-2 pr-4 font-medium">{t("perf.state")}</th>
                  <th className="py-2 pr-4 font-medium">{t("perf.current")}</th>
                  <th className="py-2 pr-4 font-medium">{t("perf.target")}</th>
                  <th className="py-2 pr-4 font-medium">{t("perf.trend")}</th>
                </tr>
              </thead>
              <tbody>
                {dims.map((d) => (
                  <tr key={d.id} className="border-b border-[var(--border)]/50">
                    <td className="px-4 py-2 font-medium">{ts(d.id)}</td>
                    <td className="py-2 pr-4">
                      <span
                        className={cn(
                          "inline-flex rounded-full border px-2 py-0.5 text-xs",
                          toneBg[d.tone],
                        )}
                      >
                        {tst(d.stateKey)}
                      </span>
                    </td>
                    <td className="py-2 pr-4 tabular-nums">{pct(d.value)}</td>
                    <td className="py-2 pr-4 text-[var(--muted-foreground)]">≥ {pct(d.target)}</td>
                    <td className="w-24 py-2 pr-4">
                      <MetricSparkline
                        values={d.trend && d.trend.length > 1 ? d.trend : []}
                        tone={d.trend && d.trend.length > 1 ? d.tone : "neutral"}
                        className="h-6"
                        height={26}
                      />
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

// ---------------------------------------------------------------------------
// Score evolution (line chart over trend buckets)
// ---------------------------------------------------------------------------

function ScoreEvolution({ trend }: { trend?: import("@/lib/api/schemas").TrendReport }) {
  const t = useTranslations("quality");
  const values = trend?.buckets.map((b) => b.mean) ?? [];
  const dirTone: OverviewTone =
    trend?.direction === "improving"
      ? "success"
      : trend?.direction === "degrading"
        ? "danger"
        : "info";
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm">{t("evolution.title")}</CardTitle>
        {trend ? (
          <Badge className={toneBg[dirTone]}>{t(`evolution.${trend.direction}`)}</Badge>
        ) : null}
      </CardHeader>
      <CardContent>
        {values.length > 1 ? (
          <div className="rounded-md border border-[var(--border)] bg-[var(--muted)]/20 p-3">
            <MetricSparkline values={values} tone={dirTone} className="h-24" height={96} />
            <div className="mt-2 flex items-center justify-between text-[0.65rem] text-[var(--muted-foreground)]">
              <span>{t("evolution.points", { n: values.length })}</span>
              <span className="tabular-nums">
                {trend
                  ? `${trend.first_half_mean.toFixed(2)} → ${trend.second_half_mean.toFixed(2)}`
                  : ""}
              </span>
            </div>
          </div>
        ) : (
          <p className="py-10 text-center text-sm text-[var(--muted-foreground)]">
            {t("evolution.empty")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Radar — quality dimensions
// ---------------------------------------------------------------------------

function RadarCard({ dims }: { dims: DimRow[] }) {
  const t = useTranslations("quality");
  const ts = useTranslations("quality.signals");
  return (
    <Card className="rounded-lg">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{t("dimensions.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {dims.length >= 3 ? (
          <Radar points={dims.map((d) => ({ label: ts(d.id), value: d.value }))} />
        ) : (
          <p className="py-10 text-center text-sm text-[var(--muted-foreground)]">{t("empty")}</p>
        )}
      </CardContent>
    </Card>
  );
}

function Radar({ points }: { points: { label: string; value: number }[] }) {
  const size = 220;
  const c = size / 2;
  const r = size / 2 - 30;
  const n = points.length;
  const angle = (i: number) => (Math.PI * 2 * i) / n - Math.PI / 2;
  const at = (i: number, radius: number) => ({
    x: c + radius * Math.cos(angle(i)),
    y: c + radius * Math.sin(angle(i)),
  });
  const poly = points
    .map((p, i) => {
      const pt = at(i, r * Math.max(0.04, p.value));
      return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
    })
    .join(" ");
  const rings = [0.25, 0.5, 0.75, 1];
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto h-auto w-full max-w-[260px]">
      <title>Radar</title>
      {rings.map((ring) => (
        <polygon
          key={ring}
          points={points
            .map((_, i) => {
              const pt = at(i, r * ring);
              return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
            })
            .join(" ")}
          fill="none"
          stroke="var(--border)"
          strokeWidth="1"
        />
      ))}
      {points.map((p, i) => {
        const pt = at(i, r);
        return (
          <line
            key={`spoke-${p.label}`}
            x1={c}
            y1={c}
            x2={pt.x}
            y2={pt.y}
            stroke="var(--border)"
            strokeWidth="1"
          />
        );
      })}
      <polygon points={poly} fill="rgb(59 160 255 / 0.22)" stroke="#3ba0ff" strokeWidth="2" />
      {points.map((p, i) => {
        const pt = at(i, r + 14);
        return (
          <text
            key={`lbl-${p.label}`}
            x={pt.x}
            y={pt.y}
            textAnchor="middle"
            dominantBaseline="middle"
            className="fill-[var(--muted-foreground)] text-[8px]"
          >
            {p.label}
          </text>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Donut
// ---------------------------------------------------------------------------

function DonutCard({
  title,
  slices,
  loading,
}: {
  title: string;
  slices: { label: string; value: number; color: string }[];
  loading: boolean;
}) {
  const t = useTranslations("quality");
  const total = slices.reduce((s, x) => s + x.value, 0);
  return (
    <Card className="rounded-lg">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[9rem] items-center gap-4">
        {loading ? (
          <Skeleton className="h-28 w-full" />
        ) : total === 0 ? (
          <p className="w-full py-8 text-center text-sm text-[var(--muted-foreground)]">
            {t("empty")}
          </p>
        ) : (
          <>
            <Donut slices={slices} total={total} />
            <ul className="flex min-w-0 flex-1 flex-col gap-1 text-xs">
              {slices.slice(0, 6).map((s) => (
                <li key={s.label} className="grid grid-cols-[auto_1fr_auto] items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
                  <span className="truncate text-[var(--muted-foreground)]">{s.label}</span>
                  <span className="tabular-nums">{Math.round((s.value / total) * 100)}%</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Donut({
  slices,
  total,
}: {
  slices: { label: string; value: number; color: string }[];
  total: number;
}) {
  const size = 104;
  const stroke = 16;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="h-28 w-28 shrink-0 -rotate-90">
      <title>Donut</title>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--muted)"
        strokeWidth={stroke}
      />
      {slices.map((s) => {
        const frac = s.value / total;
        const dash = frac * circ;
        const el = (
          <circle
            key={s.label}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={stroke}
            strokeDasharray={`${dash} ${circ - dash}`}
            strokeDashoffset={-offset}
          />
        );
        offset += dash;
        return el;
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Diagnostic (roadmap-derived recommendations)
// ---------------------------------------------------------------------------

const severityTone: Record<string, OverviewTone> = {
  high: "danger",
  medium: "warning",
  low: "neutral",
};

function DiagnosticCard({
  items,
  loading,
  n,
}: {
  items: import("@/lib/api/schemas").RoadmapReport["items"];
  loading: boolean;
  n: number;
}) {
  const t = useTranslations("quality");
  return (
    <Card className="rounded-lg">
      <CardHeader className="flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm">{t("diagnostic.title")}</CardTitle>
        <Badge tone="neutral">{n}</Badge>
      </CardHeader>
      <CardContent className="flex min-h-[6rem] flex-col gap-2">
        {loading ? (
          <Skeleton className="h-20 w-full" />
        ) : items.length === 0 ? (
          <p className="py-6 text-center text-sm text-emerald-400">{t("diagnostic.empty")}</p>
        ) : (
          items.slice(0, 4).map((item) => (
            <div
              key={item.signal}
              className="rounded-md border border-[var(--border)] bg-[var(--muted)]/20 p-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{item.theme}</span>
                <Badge className={toneBg[severityTone[item.severity] ?? "neutral"]}>
                  {item.severity}
                </Badge>
              </div>
              <p className="mt-1 text-[0.7rem] text-[var(--muted-foreground)]">{item.suggestion}</p>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Recent eval activity
// ---------------------------------------------------------------------------

function ActivityCard({
  scores,
  loading,
}: {
  scores?: import("@/lib/api/schemas").EvalScore[];
  loading: boolean;
}) {
  const t = useTranslations("quality");
  const rows = scores ? [...scores].reverse().slice(0, 7) : [];
  return (
    <Card className="rounded-lg">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{t("activity.title")}</CardTitle>
      </CardHeader>
      <CardContent className="flex min-h-[6rem] flex-col gap-2">
        {loading ? (
          <Skeleton className="h-16 w-full" />
        ) : rows.length === 0 ? (
          <p className="py-4 text-center text-xs text-[var(--muted-foreground)]">
            {t("activity.empty")}
          </p>
        ) : (
          rows.map((s, i) => (
            <div
              key={`${s.scored_at}-${i}`}
              className="grid grid-cols-[auto_1fr_auto] items-center gap-2 text-xs"
            >
              <span className={cn("h-2 w-2 rounded-full", dotBg[rateTone(s.score)])} />
              <span className="truncate">
                {s.metric} · <span className="uppercase">{s.language}</span>
              </span>
              <span className="font-mono tabular-nums text-[var(--muted-foreground)]">
                {s.score.toFixed(2)}
              </span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

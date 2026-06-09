"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  BookCheck,
  Coins,
  Crosshair,
  ExternalLink,
  Filter,
  Flame,
  Gauge,
  GitCompareArrows,
  GitFork,
  Hash,
  Landmark,
  Languages,
  Layers,
  LineChart,
  ListFilter,
  Lock,
  Microscope,
  Receipt,
  Route,
  Scale,
  ShieldCheck,
  SlidersHorizontal,
  Target,
  TrendingDown,
  Wrench,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { ReplayPanel } from "@/components/observability/replay-panel";
import { SessionTheater } from "@/components/observability/session-theater";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchAnomalies,
  fetchCalibration,
  fetchCitations,
  fetchConformance,
  fetchContradictions,
  fetchCost,
  fetchEvalScores,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchGuardExplain,
  fetchIntent,
  fetchLocaleFormat,
  fetchObsCost,
  fetchPiiLeak,
  fetchRedteam,
  fetchRefusal,
  fetchRouting,
  fetchSLO,
  fetchSessions,
  fetchTailSampling,
  fetchToolValidity,
  fetchTrend,
  fetchWhatChanged,
  runRedteam,
  runShadow,
} from "@/lib/api/client";
import type {
  AnomalyReport,
  Calibration,
  CitationSummary,
  ConformanceReport,
  ContradictionReport,
  CostReport,
  EvalScore,
  FirewallEfficacy,
  FunnelReport,
  GuardExplainReport,
  IntentReport,
  LocaleFormatSummary,
  ObsCostReport,
  PIILeakSummary,
  RedTeamResponse,
  RefusalReport,
  RoutingReport,
  SLOReport,
  SessionReport,
  ShadowReport,
  TailSamplingReport,
  ToolValidity,
  TrendReport,
  WhatChanged,
} from "@/lib/api/schemas";

// Locally-available Ollama models to shadow against (smallest first).
const SHADOW_MODELS = ["llama3.2:3b", "mistral:7b", "gemma3:27b", "llama3.3:70b"] as const;

const POLL_MS = 5_000;
const PHOENIX_URL = process.env.NEXT_PUBLIC_PHOENIX_URL ?? "http://localhost:16006";
const LANGFUSE_URL = process.env.NEXT_PUBLIC_LANGFUSE_URL ?? "http://localhost:3900";

function scoreTone(score: number): string {
  if (score >= 0.8) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 0.5) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function ObservabilityDashboard() {
  const t = useTranslations("observability");

  const scores = useQuery({
    queryKey: ["eval-scores"],
    queryFn: ({ signal }) => fetchEvalScores(signal),
    refetchInterval: POLL_MS,
  });

  const slo = useQuery({
    queryKey: ["slo"],
    queryFn: ({ signal }) => fetchSLO(signal),
    refetchInterval: POLL_MS,
  });

  const tailSampling = useQuery({
    queryKey: ["tail-sampling"],
    queryFn: ({ signal }) => fetchTailSampling(signal),
    refetchInterval: 15_000,
  });

  const trend = useQuery({
    queryKey: ["trend"],
    queryFn: ({ signal }) => fetchTrend(signal),
    refetchInterval: 15_000,
  });

  // The obs-cost benchmark is stable per process and cached server-side; fetch once.
  const obsCost = useQuery({
    queryKey: ["obs-cost"],
    queryFn: ({ signal }) => fetchObsCost(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  // Calibration is computed server-side (slow, judge over a gold set) and cached,
  // so fetch it once rather than polling.
  const calibration = useQuery({
    queryKey: ["calibration"],
    queryFn: ({ signal }) => fetchCalibration(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const firewall = useQuery({
    queryKey: ["firewall-efficacy"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const tools = useQuery({
    queryKey: ["tool-validity"],
    queryFn: ({ signal }) => fetchToolValidity(signal),
    refetchInterval: 15_000,
  });

  const routing = useQuery({
    queryKey: ["routing"],
    queryFn: ({ signal }) => fetchRouting(signal),
    refetchInterval: 15_000,
  });

  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: ({ signal }) => fetchSessions(signal),
    refetchInterval: 15_000,
  });

  const piiLeak = useQuery({
    queryKey: ["pii-leak"],
    queryFn: ({ signal }) => fetchPiiLeak(signal),
    refetchInterval: 15_000,
  });

  const contradictions = useQuery({
    queryKey: ["contradictions"],
    queryFn: ({ signal }) => fetchContradictions(signal),
    refetchInterval: 20_000,
  });

  const whatChanged = useQuery({
    queryKey: ["what-changed"],
    queryFn: ({ signal }) => fetchWhatChanged(signal),
    refetchInterval: 20_000,
  });

  const anomalies = useQuery({
    queryKey: ["anomalies"],
    queryFn: ({ signal }) => fetchAnomalies(signal),
    refetchInterval: 20_000,
  });

  const refusal = useQuery({
    queryKey: ["refusal"],
    queryFn: ({ signal }) => fetchRefusal(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const citations = useQuery({
    queryKey: ["citations"],
    queryFn: ({ signal }) => fetchCitations(signal),
    refetchInterval: 15_000,
  });

  const localeFormat = useQuery({
    queryKey: ["locale-format"],
    queryFn: ({ signal }) => fetchLocaleFormat(signal),
    refetchInterval: 15_000,
  });

  const conformance = useQuery({
    queryKey: ["conformance"],
    queryFn: ({ signal }) => fetchConformance(signal),
    refetchInterval: 15_000,
  });

  const intent = useQuery({
    queryKey: ["intent"],
    queryFn: ({ signal }) => fetchIntent(signal),
    refetchInterval: 15_000,
  });

  const cost = useQuery({
    queryKey: ["cost"],
    queryFn: ({ signal }) => fetchCost(signal),
    refetchInterval: 15_000,
  });

  const guardExplain = useQuery({
    queryKey: ["guard-explain"],
    queryFn: ({ signal }) => fetchGuardExplain(signal),
    refetchInterval: 15_000,
  });

  const funnel = useQuery({
    queryKey: ["funnel"],
    queryFn: ({ signal }) => fetchFunnel(signal),
    refetchInterval: 15_000,
  });

  // Newest first for display.
  const rows: EvalScore[] = scores.data ? [...scores.data.scores].reverse() : [];

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <BackendCard
          title="Arize Phoenix"
          subtitle={t("phoenix")}
          href={PHOENIX_URL}
          icon={<LineChart className="h-5 w-5 text-blue-500" />}
        />
        <BackendCard
          title="Langfuse"
          subtitle={t("langfuse")}
          href={LANGFUSE_URL}
          icon={<Gauge className="h-5 w-5 text-blue-500" />}
        />
      </div>

      <SLOCard data={slo.data} loading={slo.isLoading} />

      <ShadowCard />

      <TailSamplingCard data={tailSampling.data} loading={tailSampling.isLoading} />

      <TrendCard data={trend.data} loading={trend.isLoading} />

      <ObsCostCard data={obsCost.data} loading={obsCost.isLoading} />

      <CalibrationCard data={calibration.data} loading={calibration.isLoading} />

      <CitationCard data={citations.data} loading={citations.isLoading} />

      <LocaleFormatCard data={localeFormat.data} loading={localeFormat.isLoading} />

      <FirewallEfficacyCard data={firewall.data} loading={firewall.isLoading} />

      <RedTeamCard />

      <RefusalCard data={refusal.data} loading={refusal.isLoading} />

      <PiiLeakCard data={piiLeak.data} loading={piiLeak.isLoading} />

      <ToolValidityCard data={tools.data} loading={tools.isLoading} />

      <ConformanceCard data={conformance.data} loading={conformance.isLoading} />

      <GuardExplainCard data={guardExplain.data} loading={guardExplain.isLoading} />

      <RoutingCard data={routing.data} loading={routing.isLoading} />

      <IntentCard data={intent.data} loading={intent.isLoading} />

      <SessionCard data={sessions.data} loading={sessions.isLoading} />

      <FunnelCard data={funnel.data} loading={funnel.isLoading} />

      <ContradictionCard data={contradictions.data} loading={contradictions.isLoading} />

      <AnomalyCard data={anomalies.data} loading={anomalies.isLoading} />

      <CostCard data={cost.data} loading={cost.isLoading} />

      <WhatChangedCard data={whatChanged.data} loading={whatChanged.isLoading} />

      <SessionTheater />

      <ReplayPanel />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            {t("scores.title")}
            <Badge tone="neutral">{t("scores.metric")}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {scores.isLoading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : rows.length === 0 ? (
            <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
              {t("scores.empty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="py-2 pr-4 font-medium">{t("scores.time")}</th>
                    <th className="py-2 pr-4 font-medium">{t("scores.metricCol")}</th>
                    <th className="py-2 pr-4 font-medium">{t("scores.score")}</th>
                    <th className="py-2 pr-4 font-medium">{t("scores.language")}</th>
                    <th className="py-2 font-medium">{t("scores.judge")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((s, i) => (
                    <tr key={`${s.scored_at}-${i}`} className="border-b border-[var(--border)]/50">
                      <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                        {new Date(s.scored_at).toLocaleTimeString()}
                      </td>
                      <td className="py-2 pr-4">{s.metric}</td>
                      <td className={`py-2 pr-4 font-semibold tabular-nums ${scoreTone(s.score)}`}>
                        {s.score.toFixed(2)}
                      </td>
                      <td className="py-2 pr-4 uppercase">{s.language}</td>
                      <td className="py-2 text-[var(--muted-foreground)]">{s.judge_model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function BackendCard({
  title,
  subtitle,
  href,
  icon,
}: {
  title: string;
  subtitle: string;
  href: string;
  icon: ReactNode;
}) {
  return (
    <a href={href} target="_blank" rel="noreferrer noopener" className="group">
      <Card className="h-full transition-colors hover:border-blue-500/50">
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2 text-sm">
            <span className="flex items-center gap-2">
              {icon}
              {title}
            </span>
            <ExternalLink className="h-4 w-4 text-[var(--muted-foreground)] transition-colors group-hover:text-blue-500" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-[var(--muted-foreground)]">{subtitle}</p>
        </CardContent>
      </Card>
    </a>
  );
}

function SLOCard({ data, loading }: { data: SLOReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const remaining = data ? Math.round(data.budget_remaining * 100) : 100;
  const burnTone = !data || data.burn_rate <= 1 ? "success" : data.breaching ? "danger" : "warning";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Flame className="h-4 w-4 text-blue-500" />
          {t("slo.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("slo.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("slo.objective")}</span>
                <span className="font-semibold tabular-nums">
                  {Math.round(data.target * 100)}% ≥ {data.threshold.toFixed(2)}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("slo.attained")}</span>
                <span className={`font-semibold tabular-nums ${scoreTone(data.good_rate)}`}>
                  {Math.round(data.good_rate * 100)}%
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("slo.budget")}</span>
                <Badge tone={remaining >= 50 ? "success" : remaining > 0 ? "warning" : "danger"}>
                  {remaining}%
                </Badge>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("slo.burnRate")}</span>
                <Badge tone={burnTone}>{data.burn_rate.toFixed(1)}×</Badge>
              </div>
              <Metric label={t("slo.fastBurn")} value={`${data.burn_rate_fast.toFixed(1)}×`} />
              <Metric label={t("slo.bad")} value={`${data.n_bad}/${data.n}`} />
            </div>
            {data.breaching ? (
              <p className="text-xs text-red-600 dark:text-red-400">{t("slo.breaching")}</p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ShadowCard() {
  const t = useTranslations("observability");
  const [model, setModel] = useState<string>(SHADOW_MODELS[1]);
  const mutation = useMutation({
    mutationFn: () => runShadow(model),
  });
  const data: ShadowReport | undefined = mutation.data;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-blue-500" />
            {t("shadow.title")}
          </span>
          <div className="flex items-center gap-2">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-1 text-xs"
            >
              {SHADOW_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? t("shadow.running") : t("shadow.run")}
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!data ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("shadow.empty")}</p>
        ) : data.n_compared === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("shadow.noTraffic")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("shadow.delta")}</span>
                <Badge tone={data.mean_delta >= 0 ? "success" : "danger"}>
                  {data.mean_delta >= 0 ? "+" : ""}
                  {data.mean_delta.toFixed(2)}
                </Badge>
              </div>
              <Metric label={t("shadow.wins")} value={String(data.wins)} />
              <Metric label={t("shadow.losses")} value={String(data.losses)} />
              <Metric label={t("shadow.ties")} value={String(data.ties)} />
              <Metric
                label={t("shadow.scores")}
                value={`${data.mean_original_score.toFixed(2)} → ${data.mean_candidate_score.toFixed(2)}`}
              />
              <Metric
                label={t("shadow.similarity")}
                value={`${Math.round(data.mean_similarity * 100)}%`}
              />
            </div>
            <ul className="flex flex-col gap-1 text-xs">
              {data.comparisons.map((c, i) => (
                <li key={`${i}-${c.question.slice(0, 12)}`} className="flex items-center gap-2">
                  <Badge
                    tone={
                      c.outcome === "win" ? "success" : c.outcome === "loss" ? "danger" : "neutral"
                    }
                  >
                    {c.outcome === "win" ? "+" : c.outcome === "loss" ? "" : "±"}
                    {c.score_delta.toFixed(2)}
                  </Badge>
                  <span className="uppercase text-[var(--muted-foreground)]">{c.language}</span>
                  <span className="min-w-0 truncate">{c.question}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TailSamplingCard({
  data,
  loading,
}: {
  data: TailSamplingReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const tailKept = data ? Math.round(data.tail_retention_rate * 100) : 100;
  const retained = data ? Math.round(data.retention_rate * 100) : 100;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ListFilter className="h-4 w-4 text-blue-500" />
          {t("tailSampling.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_traces === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("tailSampling.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("tailSampling.tailKept")}
              </span>
              <Badge tone={tailKept === 100 ? "success" : "danger"}>{tailKept}%</Badge>
            </div>
            <Metric label={t("tailSampling.retained")} value={`${retained}%`} />
            <Metric label={t("tailSampling.tail")} value={`${data.n_tail}/${data.n_traces}`} />
            <Metric label={t("tailSampling.slow")} value={String(data.n_slow)} />
            <Metric label={t("tailSampling.lowScore")} value={String(data.n_low_score)} />
            <Metric label={t("tailSampling.kept")} value={`${data.n_kept}/${data.n_traces}`} />
            <Metric
              label={t("tailSampling.baseRate")}
              value={`${Math.round(data.base_rate * 100)}%`}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TrendCard({ data, loading }: { data: TrendReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const directionTone =
    data?.direction === "improving"
      ? "success"
      : data?.direction === "degrading"
        ? "danger"
        : "neutral";
  // Sparkline scaling over the bucket means.
  const means = data?.buckets.map((b) => b.mean) ?? [];
  const lo = means.length > 0 ? Math.min(...means) : 0;
  const hi = means.length > 0 ? Math.max(...means) : 1;
  const span = hi - lo || 1;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <TrendingDown className="h-4 w-4 text-blue-500" />
          {t("trend.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("trend.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("trend.direction")}
                </span>
                <Badge tone={directionTone}>{t(`trend.${data.direction}`)}</Badge>
              </div>
              <Metric label={t("trend.slope")} value={data.slope.toFixed(4)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("trend.delta")}</span>
                <span
                  className={`font-semibold tabular-nums ${
                    data.delta >= 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  {data.delta >= 0 ? "+" : ""}
                  {data.delta.toFixed(2)}
                </span>
              </div>
              <Metric
                label={t("trend.halves")}
                value={`${data.first_half_mean.toFixed(2)} → ${data.second_half_mean.toFixed(2)}`}
              />
              <Metric label={t("trend.points")} value={String(data.n)} />
            </div>
            {means.length > 1 ? (
              <div className="flex h-10 items-end gap-1">
                {data.buckets.map((b) => (
                  <div
                    key={b.index}
                    className={`flex-1 rounded-t ${
                      data.direction === "degrading" ? "bg-red-500/60" : "bg-blue-500/60"
                    }`}
                    style={{ height: `${10 + ((b.mean - lo) / span) * 90}%` }}
                    title={`${b.mean.toFixed(2)} (n=${b.n})`}
                  />
                ))}
              </div>
            ) : null}
            {data.degrading ? (
              <p className="text-xs text-red-600 dark:text-red-400">{t("trend.degradingNote")}</p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ObsCostCard({ data, loading }: { data: ObsCostReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Microscope className="h-4 w-4 text-blue-500" />
          {t("obsCost.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("obsCost.withinBudget")}
              </span>
              <Badge tone={data.within_budget ? "success" : "warning"}>
                {data.overhead_pct_of_budget < 0.01
                  ? "<0.01"
                  : data.overhead_pct_of_budget.toFixed(2)}
                %
              </Badge>
            </div>
            <Metric label={t("obsCost.perSpan")} value={`${data.span_overhead_us.toFixed(2)} µs`} />
            <Metric
              label={t("obsCost.perTurn")}
              value={`${data.overhead_per_turn_ms.toFixed(3)} ms`}
            />
            <Metric label={t("obsCost.spansPerTurn")} value={String(data.spans_per_turn)} />
            <Metric label={t("obsCost.budget")} value={`${Math.round(data.turn_budget_ms)} ms`} />
            <Metric
              label={t("obsCost.bytesPerTurn")}
              value={`${(data.est_bytes_per_turn / 1024).toFixed(1)} KiB`}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CalibrationCard({ data, loading }: { data: Calibration | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Scale className="h-4 w-4 text-blue-500" />
          {t("calibration.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-12 w-full" />
        ) : !data?.available ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("calibration.unavailable")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <Metric label={t("calibration.kappa")} value={(data.kappa ?? 0).toFixed(2)} />
            <Metric
              label={t("calibration.agreement")}
              value={`${Math.round((data.agreement ?? 0) * 100)}%`}
            />
            <Metric
              label={t("calibration.verbosity")}
              value={(data.verbosity_corr ?? 0).toFixed(2)}
            />
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("calibration.lenient")}
              </span>
              <Badge tone={data.lenient ? "warning" : "success"}>
                {data.lenient ? t("calibration.lenientYes") : t("calibration.lenientNo")}
              </Badge>
            </div>
            <Metric label={t("calibration.judge")} value={data.judge_model ?? "—"} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FirewallEfficacyCard({
  data,
  loading,
}: {
  data: FirewallEfficacy | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldCheck className="h-4 w-4 text-blue-500" />
          {t("firewall.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <Metric label={t("firewall.precision")} value={data.precision.toFixed(2)} />
            <Metric label={t("firewall.recall")} value={data.recall.toFixed(2)} />
            <Metric label={t("firewall.f1")} value={data.f1.toFixed(2)} />
            <Metric
              label={t("firewall.caught")}
              value={`${data.true_positive}/${data.n_positive}`}
            />
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("firewall.falsePositive")}
              </span>
              <Badge tone={data.false_positive === 0 ? "success" : "warning"}>
                {data.false_positive}
              </Badge>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RedTeamCard() {
  const t = useTranslations("observability");
  const query = useQuery({
    queryKey: ["redteam"],
    queryFn: ({ signal }) => fetchRedteam(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const mutation = useMutation({
    mutationFn: () => runRedteam(),
    onSuccess: (res: RedTeamResponse) => query.refetch().then(() => res),
  });

  const data = mutation.data ?? query.data;
  const snapshots = data?.snapshots ?? [];
  const latest = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;
  const pct = latest ? Math.round(latest.attack_success_rate * 100) : 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="flex items-center gap-2">
            <Crosshair className="h-4 w-4 text-blue-500" />
            {t("redteam.title")}
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? t("redteam.running") : t("redteam.run")}
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {!latest ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("redteam.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("redteam.successRate")}
                </span>
                <Badge tone={pct === 0 ? "success" : pct <= 20 ? "warning" : "danger"}>
                  {pct}%
                </Badge>
              </div>
              <Metric
                label={t("redteam.blocked")}
                value={`${latest.n_blocked}/${latest.n_attacks}`}
              />
              <Metric label={t("redteam.bypassed")} value={String(latest.n_bypassed)} />
              {snapshots.length > 1 ? (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {t("redteam.drift")}
                  </span>
                  <span className="flex items-center gap-1 font-mono text-xs tabular-nums">
                    {snapshots.slice(-8).map((s, i) => (
                      <span key={`${s.ran_at}-${i}`}>
                        {Math.round(s.attack_success_rate * 100)}
                      </span>
                    ))}
                  </span>
                </div>
              ) : null}
            </div>
            {latest.bypassed_samples.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
                {latest.bypassed_samples.map((s, i) => (
                  <li key={`${i}-${s.slice(0, 16)}`} className="flex items-start gap-2">
                    <span
                      aria-hidden
                      className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-amber-500"
                    />
                    <span className="min-w-0 break-words">{s}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LocaleFormatCard({
  data,
  loading,
}: {
  data: LocaleFormatSummary | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.correctness_rate * 100) : 100;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Receipt className="h-4 w-4 text-blue-500" />
          {t("localeFormat.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_amounts === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("localeFormat.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("localeFormat.correct")}
              </span>
              <Badge tone={pct === 100 ? "success" : pct >= 80 ? "warning" : "danger"}>
                {pct}%
              </Badge>
            </div>
            <Metric label={t("localeFormat.amounts")} value={String(data.n_amounts)} />
            <Metric label={t("localeFormat.violations")} value={String(data.n_violations)} />
            {data.examples.length > 0 ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("localeFormat.examples")}
                </span>
                <span className="font-mono text-xs text-red-600 dark:text-red-400">
                  {data.examples.join(", ")}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CitationCard({ data, loading }: { data: CitationSummary | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.validity_rate * 100) : 100;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <BookCheck className="h-4 w-4 text-blue-500" />
          {t("citations.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_citations === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("citations.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("citations.valid")}</span>
              <Badge tone={pct === 100 ? "success" : pct >= 80 ? "warning" : "danger"}>
                {pct}%
              </Badge>
            </div>
            <Metric label={t("citations.total")} value={String(data.n_citations)} />
            <Metric label={t("citations.fabricated")} value={String(data.n_unsupported)} />
            {data.unsupported_examples.length > 0 ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("citations.examples")}
                </span>
                <span className="font-mono text-xs text-red-600 dark:text-red-400">
                  {data.unsupported_examples.join(", ")}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RefusalCard({ data, loading }: { data: RefusalReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const over = data ? Math.round(data.over_refusal_rate * 100) : 0;
  const under = data ? Math.round(data.under_refusal_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <SlidersHorizontal className="h-4 w-4 text-blue-500" />
          {t("refusal.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("refusal.over")}</span>
              <Badge tone={over === 0 ? "success" : over <= 10 ? "warning" : "danger"}>
                {over}%
              </Badge>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("refusal.under")}</span>
              <Badge tone={under === 0 ? "success" : under <= 30 ? "warning" : "danger"}>
                {under}%
              </Badge>
            </div>
            <Metric label={t("refusal.legit")} value={`${data.legit_refused}/${data.n_legit}`} />
            <Metric
              label={t("refusal.forbidden")}
              value={`${data.forbidden_allowed}/${data.n_forbidden}`}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PiiLeakCard({ data, loading }: { data: PIILeakSummary | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.leak_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Lock className="h-4 w-4 text-blue-500" />
          {t("piiLeak.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("piiLeak.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("piiLeak.rate")}</span>
              <Badge tone={pct === 0 ? "success" : pct <= 10 ? "warning" : "danger"}>{pct}%</Badge>
            </div>
            <Metric label={t("piiLeak.turns")} value={String(data.n_turns)} />
            <Metric label={t("piiLeak.leaked")} value={String(data.total_leaked)} />
            {data.examples.length > 0 ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("piiLeak.examples")}
                </span>
                <span className="font-mono text-xs text-red-600 dark:text-red-400">
                  {data.examples.join(", ")}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GuardExplainCard({
  data,
  loading,
}: {
  data: GuardExplainReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Landmark className="h-4 w-4 text-blue-500" />
          {t("guardExplain.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_decisions === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("guardExplain.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("guardExplain.decisions")} value={String(data.n_decisions)} />
              <Metric label={t("guardExplain.denials")} value={String(data.n_denials)} />
            </div>
            <ul className="flex flex-col gap-1 text-xs">
              {data.rules.map((r) => (
                <li key={`${r.rule}-${r.decision}`} className="flex items-center gap-2">
                  <Badge
                    tone={
                      r.decision === "deny"
                        ? "danger"
                        : r.decision === "transform"
                          ? "warning"
                          : "neutral"
                    }
                  >
                    {r.decision}
                  </Badge>
                  <span className="min-w-0 flex-1 truncate font-mono text-[var(--muted-foreground)]">
                    {r.rule}
                  </span>
                  <span className="tabular-nums">{r.count}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ConformanceCard({
  data,
  loading,
}: {
  data: ConformanceReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.conformance_rate * 100) : 100;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Hash className="h-4 w-4 text-blue-500" />
          {t("conformance.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_fields_checked === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("conformance.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("conformance.rate")}
              </span>
              <Badge tone={pct === 100 ? "success" : pct >= 90 ? "warning" : "danger"}>
                {pct}%
              </Badge>
            </div>
            <Metric label={t("conformance.fields")} value={String(data.n_fields_checked)} />
            <Metric label={t("conformance.violations")} value={String(data.n_violations)} />
            {data.violations.length > 0 ? (
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("conformance.examples")}
                </span>
                <span className="font-mono text-xs text-red-600 dark:text-red-400">
                  {data.violations.join(", ")}
                </span>
              </div>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ToolValidityCard({
  data,
  loading,
}: {
  data: ToolValidity | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.validity_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Wrench className="h-4 w-4 text-blue-500" />
          {t("tools.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.total === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("tools.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("tools.validity")}</span>
              <Badge tone={pct >= 90 ? "success" : pct >= 70 ? "warning" : "danger"}>{pct}%</Badge>
            </div>
            <Metric label={t("tools.allowed")} value={String(data.allowed)} />
            <Metric label={t("tools.denied")} value={String(data.denied)} />
            <Metric label={t("tools.argFailures")} value={String(data.arg_failures)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function IntentCard({ data, loading }: { data: IntentReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const lowPct = data ? Math.round(data.low_confidence_rate * 100) : 0;
  const entries = data ? Object.entries(data.distribution).sort((a, b) => b[1] - a[1]) : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Route className="h-4 w-4 text-blue-500" />
          {t("intent.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("intent.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("intent.lowConfidence")}
                </span>
                <Badge tone={lowPct === 0 ? "success" : lowPct <= 25 ? "warning" : "danger"}>
                  {lowPct}%
                </Badge>
              </div>
              <Metric label={t("intent.turns")} value={String(data.n)} />
              <Metric label={t("intent.unknown")} value={String(data.unknown)} />
            </div>
            <div className="flex flex-wrap gap-2">
              {entries.map(([name, count]) => (
                <Badge key={name} tone="neutral">
                  {name} · {count}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RoutingCard({ data, loading }: { data: RoutingReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const mis = data ? Math.round(data.mismatch_rate * 100) : 0;
  const cs = data ? Math.round(data.code_switch_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Languages className="h-4 w-4 text-blue-500" />
          {t("routing.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("routing.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("routing.mismatch")}
              </span>
              <Badge tone={mis === 0 ? "success" : mis <= 20 ? "warning" : "danger"}>{mis}%</Badge>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("routing.codeSwitch")}
              </span>
              <Badge tone={cs === 0 ? "neutral" : "warning"}>{cs}%</Badge>
            </div>
            <Metric label={t("routing.turns")} value={String(data.n)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FunnelCard({ data, loading }: { data: FunnelReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Filter className="h-4 w-4 text-blue-500" />
          {t("funnel.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.languages.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("funnel.empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-4 font-medium">{t("funnel.language")}</th>
                  <th className="py-2 pr-4 font-medium">{t("funnel.turns")}</th>
                  <th className="py-2 pr-4 font-medium">{t("funnel.sessions")}</th>
                  <th className="py-2 pr-4 font-medium">{t("funnel.meanScore")}</th>
                  <th className="py-2 pr-4 font-medium">{t("funnel.singleTurn")}</th>
                  <th className="py-2 font-medium">{t("funnel.lowScore")}</th>
                </tr>
              </thead>
              <tbody>
                {data.languages.map((l) => (
                  <tr key={l.language} className="border-b border-[var(--border)]/50">
                    <td className="py-2 pr-4 uppercase">{l.language}</td>
                    <td className="py-2 pr-4 tabular-nums">{l.n_turns}</td>
                    <td className="py-2 pr-4 tabular-nums">{l.n_sessions}</td>
                    <td
                      className={`py-2 pr-4 font-semibold tabular-nums ${scoreTone(l.mean_score)}`}
                    >
                      {l.mean_score.toFixed(2)}
                    </td>
                    <td className="py-2 pr-4 tabular-nums">
                      {Math.round(l.single_turn_rate * 100)}%
                    </td>
                    <td className="py-2 tabular-nums">{Math.round(l.low_score_rate * 100)}%</td>
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

function SessionCard({ data, loading }: { data: SessionReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Target className="h-4 w-4 text-blue-500" />
          {t("sessions.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_sessions === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("sessions.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <Metric label={t("sessions.sessions")} value={String(data.n_sessions)} />
            <Metric
              label={t("sessions.turnsPerSession")}
              value={data.mean_turns_per_session.toFixed(1)}
            />
            <Metric
              label={t("sessions.singleTurn")}
              value={`${Math.round(data.single_turn_rate * 100)}%`}
            />
            <Metric label={t("sessions.meanScore")} value={data.mean_score.toFixed(2)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CostCard({ data, loading }: { data: CostReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Coins className="h-4 w-4 text-blue-500" />
          {t("cost.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("cost.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("cost.anomalies")}
                </span>
                <Badge tone={data.n_anomalies === 0 ? "success" : "warning"}>
                  {data.n_anomalies}
                </Badge>
              </div>
              <Metric
                label={t("cost.mean")}
                value={Math.round(data.mean_tokens).toLocaleString()}
              />
              <Metric label={t("cost.max")} value={data.max_tokens.toLocaleString()} />
              <Metric label={t("cost.total")} value={data.total_tokens.toLocaleString()} />
            </div>
            {data.anomalies.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs">
                {data.anomalies.slice(0, 5).map((a, i) => (
                  <li key={`${i}-${a.question.slice(0, 12)}`} className="flex items-center gap-2">
                    <span aria-hidden className="h-2 w-2 shrink-0 rounded-full bg-amber-500" />
                    <span className="tabular-nums text-[var(--muted-foreground)]">
                      {a.tokens.toLocaleString()}
                    </span>
                    <span className="min-w-0 truncate">{a.question}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AnomalyCard({ data, loading }: { data: AnomalyReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const flagged = data?.sessions.filter((s) => s.anomalous) ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Activity className="h-4 w-4 text-blue-500" />
          {t("anomalies.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_sessions === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("anomalies.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("anomalies.flagged")}
                </span>
                <Badge tone={data.n_anomalous === 0 ? "success" : "warning"}>
                  {data.n_anomalous}/{data.n_sessions}
                </Badge>
              </div>
            </div>
            {flagged.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs">
                {flagged.slice(0, 5).map((s) => (
                  <li key={s.conversation_id} className="flex items-center gap-2">
                    <span className="text-[var(--muted-foreground)]">
                      {s.n_turns} {t("anomalies.turns")}
                    </span>
                    {s.reasons.map((r) => (
                      <Badge key={r} tone="warning">
                        {t(`anomalies.reason.${r}`)}
                      </Badge>
                    ))}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function WhatChangedCard({ data, loading }: { data: WhatChanged | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const changes = data?.changes ?? [];
  const delta = data?.score_delta ?? 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitFork className="h-4 w-4 text-blue-500" />
          {t("whatChanged.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-12 w-full" />
        ) : !data?.available ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("whatChanged.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("whatChanged.delta")}
                </span>
                <Badge tone={delta >= 0 ? "success" : "danger"}>
                  {delta >= 0 ? "+" : ""}
                  {delta.toFixed(2)}
                </Badge>
              </div>
              {data.attributed ? (
                <Badge tone="warning">{t("whatChanged.attributed")}</Badge>
              ) : (
                <Badge tone="neutral">
                  {data.regressed ? t("whatChanged.unexplained") : t("whatChanged.stable")}
                </Badge>
              )}
            </div>
            {changes.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs">
                {changes.map((c) => (
                  <li key={c.field} className="flex items-center gap-2">
                    <span className="w-32 shrink-0 font-mono text-[var(--muted-foreground)]">
                      {c.field}
                    </span>
                    <span className="font-mono">{c.before}</span>
                    <span className="text-[var(--muted-foreground)]">→</span>
                    <span className="font-mono text-amber-600 dark:text-amber-400">{c.after}</span>
                  </li>
                ))}
              </ul>
            ) : null}
            {(data.docs_added?.length ?? 0) + (data.docs_removed?.length ?? 0) > 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">
                {t("whatChanged.docs")}: +{data.docs_added?.length ?? 0} / −
                {data.docs_removed?.length ?? 0}
              </p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ContradictionCard({
  data,
  loading,
}: {
  data: ContradictionReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitCompareArrows className="h-4 w-4 text-blue-500" />
          {t("contradiction.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("contradiction.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("contradiction.found")}
                </span>
                <Badge tone={data.n_contradictions === 0 ? "success" : "danger"}>
                  {data.n_contradictions}
                </Badge>
              </div>
              <Metric label={t("contradiction.sessions")} value={String(data.n_sessions)} />
              <Metric label={t("contradiction.turns")} value={String(data.n_turns)} />
            </div>
            {data.pairs.length > 0 ? (
              <ul className="flex flex-col gap-2 text-xs">
                {data.pairs.slice(0, 5).map((p, idx) => (
                  <li
                    key={`${p.conversation_id}-${p.i}-${p.j}-${idx}`}
                    className="rounded-md bg-[var(--muted)]/40 p-2"
                  >
                    <p className="text-[var(--muted-foreground)]">
                      {t("contradiction.turn")} {p.i + 1} ↔ {p.j + 1} · {t("contradiction.topic")}{" "}
                      {Math.round(p.topic_similarity * 100)}% · {t("contradiction.answers")}{" "}
                      {Math.round(p.answer_similarity * 100)}%
                    </p>
                    <p className="mt-0.5 break-words">
                      “{p.question_i}” / “{p.question_j}”
                    </p>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className="font-semibold tabular-nums">{value}</span>
    </div>
  );
}

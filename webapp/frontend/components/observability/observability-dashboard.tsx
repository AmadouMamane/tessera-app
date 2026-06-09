"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Archive,
  BadgeCheck,
  Ban,
  BookCheck,
  Boxes,
  Brain,
  CalendarClock,
  Coins,
  Crosshair,
  Eraser,
  ExternalLink,
  Filter,
  Flame,
  Footprints,
  Gauge,
  GitCompareArrows,
  GitFork,
  Globe,
  Grid3x3,
  Hash,
  KeyRound,
  Landmark,
  Languages,
  Layers,
  LineChart,
  ListChecks,
  ListFilter,
  Lock,
  Microscope,
  Radar,
  Radio,
  Receipt,
  Route,
  Scale,
  ShieldCheck,
  Siren,
  SlidersHorizontal,
  Sparkles,
  Sprout,
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
  fetchAIAct,
  fetchAnomalies,
  fetchCalibration,
  fetchCitations,
  fetchConformance,
  fetchContradictions,
  fetchCorpusFreshness,
  fetchCost,
  fetchCrossTenant,
  fetchEmbeddingInversion,
  fetchEmbeddingSkew,
  fetchErasureCoverage,
  fetchEvalScores,
  fetchFailureClusters,
  fetchFailurePredictor,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchGuardExplain,
  fetchIntent,
  fetchJourney,
  fetchLeastPrivilege,
  fetchLocaleFormat,
  fetchLocalization,
  fetchMemoryInventory,
  fetchMemoryObs,
  fetchObsCost,
  fetchPiiLeak,
  fetchPlaybooks,
  fetchRedteam,
  fetchRefusal,
  fetchRoadmap,
  fetchRouting,
  fetchSLO,
  fetchSessions,
  fetchSftDataset,
  fetchSiem,
  fetchTailSampling,
  fetchToolValidity,
  fetchToxicity,
  fetchTrend,
  fetchWhatChanged,
  runRedteam,
  runShadow,
} from "@/lib/api/client";
import type {
  AIActReport,
  AnomalyReport,
  Calibration,
  CitationSummary,
  ClusterReport,
  ConformanceReport,
  ContradictionReport,
  CostReport,
  CrossTenantReport,
  ErasureCoverage,
  EvalScore,
  FirewallEfficacy,
  FreshnessReport,
  FunnelReport,
  GuardExplainReport,
  IntentReport,
  InventoryReport,
  InversionReport,
  JourneyReport,
  LocaleFormatSummary,
  LocalizationReport,
  MemoryObsReport,
  ObsCostReport,
  PIILeakSummary,
  PlaybookReport,
  PredictorEvaluation,
  PrivilegeReport,
  RedTeamResponse,
  RefusalReport,
  RoadmapReport,
  RoutingReport,
  SFTDataset,
  SLOReport,
  SessionReport,
  ShadowReport,
  SiemExport,
  SkewReport,
  TailSamplingReport,
  ToolValidity,
  ToxicityReport,
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

  // Embedding fingerprint is stable per process; fetch once.
  const embeddingSkew = useQuery({
    queryKey: ["embedding-skew"],
    queryFn: ({ signal }) => fetchEmbeddingSkew(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const corpusFreshness = useQuery({
    queryKey: ["corpus-freshness"],
    queryFn: ({ signal }) => fetchCorpusFreshness(signal),
    refetchInterval: 60_000,
  });

  const roadmap = useQuery({
    queryKey: ["roadmap"],
    queryFn: ({ signal }) => fetchRoadmap(signal),
    refetchInterval: 20_000,
  });

  const memoryObs = useQuery({
    queryKey: ["memory-obs"],
    queryFn: ({ signal }) => fetchMemoryObs(signal),
    refetchInterval: 15_000,
  });

  // Failure clustering embeds the whole corpus and is cached server-side; fetch once.
  const failureClusters = useQuery({
    queryKey: ["failure-clusters"],
    queryFn: ({ signal }) => fetchFailureClusters(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const failurePredictor = useQuery({
    queryKey: ["failure-predictor"],
    queryFn: ({ signal }) => fetchFailurePredictor(signal),
    refetchInterval: 15_000,
  });

  const sftDataset = useQuery({
    queryKey: ["sft-dataset"],
    queryFn: ({ signal }) => fetchSftDataset(signal),
    refetchInterval: 15_000,
  });

  const toxicity = useQuery({
    queryKey: ["toxicity"],
    queryFn: ({ signal }) => fetchToxicity(signal),
    refetchInterval: 15_000,
  });

  const crossTenant = useQuery({
    queryKey: ["cross-tenant"],
    queryFn: ({ signal }) => fetchCrossTenant(signal),
    refetchInterval: 15_000,
  });

  const leastPrivilege = useQuery({
    queryKey: ["least-privilege"],
    queryFn: ({ signal }) => fetchLeastPrivilege(signal),
    refetchInterval: 15_000,
  });

  const playbooks = useQuery({
    queryKey: ["playbooks"],
    queryFn: ({ signal }) => fetchPlaybooks(signal),
    refetchInterval: 15_000,
  });

  const siem = useQuery({
    queryKey: ["siem"],
    queryFn: ({ signal }) => fetchSiem(signal),
    refetchInterval: 15_000,
  });

  const localization = useQuery({
    queryKey: ["localization"],
    queryFn: ({ signal }) => fetchLocalization(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const aiAct = useQuery({
    queryKey: ["ai-act"],
    queryFn: ({ signal }) => fetchAIAct(signal),
    refetchInterval: 30_000,
  });

  const journey = useQuery({
    queryKey: ["journey"],
    queryFn: ({ signal }) => fetchJourney(signal),
    refetchInterval: 20_000,
  });

  const memoryInventory = useQuery({
    queryKey: ["memory-inventory"],
    queryFn: ({ signal }) => fetchMemoryInventory(signal),
    refetchInterval: 20_000,
  });

  const erasureCoverage = useQuery({
    queryKey: ["erasure-coverage"],
    queryFn: ({ signal }) => fetchErasureCoverage(signal),
    refetchInterval: 20_000,
  });

  // The inversion demo embeds a fixed corpus and is cached server-side; fetch once.
  const embeddingInversion = useQuery({
    queryKey: ["embedding-inversion"],
    queryFn: ({ signal }) => fetchEmbeddingInversion(signal),
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

      <AIActCard data={aiAct.data} loading={aiAct.isLoading} />

      <PlaybooksCard data={playbooks.data} loading={playbooks.isLoading} />

      <RoadmapCard data={roadmap.data} loading={roadmap.isLoading} />

      <FailureClusterCard data={failureClusters.data} loading={failureClusters.isLoading} />

      <FailurePredictorCard data={failurePredictor.data} loading={failurePredictor.isLoading} />

      <SftDatasetCard data={sftDataset.data} loading={sftDataset.isLoading} />

      <ShadowCard />

      <TailSamplingCard data={tailSampling.data} loading={tailSampling.isLoading} />

      <TrendCard data={trend.data} loading={trend.isLoading} />

      <ObsCostCard data={obsCost.data} loading={obsCost.isLoading} />

      <EmbeddingSkewCard data={embeddingSkew.data} loading={embeddingSkew.isLoading} />

      <CorpusFreshnessCard data={corpusFreshness.data} loading={corpusFreshness.isLoading} />

      <MemoryObsCard data={memoryObs.data} loading={memoryObs.isLoading} />

      <JourneyCard data={journey.data} loading={journey.isLoading} />

      <MemoryInventoryCard data={memoryInventory.data} loading={memoryInventory.isLoading} />

      <ErasureCoverageCard data={erasureCoverage.data} loading={erasureCoverage.isLoading} />

      <InversionCard data={embeddingInversion.data} loading={embeddingInversion.isLoading} />

      <CalibrationCard data={calibration.data} loading={calibration.isLoading} />

      <CitationCard data={citations.data} loading={citations.isLoading} />

      <LocaleFormatCard data={localeFormat.data} loading={localeFormat.isLoading} />

      <FirewallEfficacyCard data={firewall.data} loading={firewall.isLoading} />

      <RedTeamCard />

      <ToxicityCard data={toxicity.data} loading={toxicity.isLoading} />

      <CrossTenantCard data={crossTenant.data} loading={crossTenant.isLoading} />

      <LeastPrivilegeCard data={leastPrivilege.data} loading={leastPrivilege.isLoading} />

      <SiemCard data={siem.data} loading={siem.isLoading} />

      <LocalizationCard data={localization.data} loading={localization.isLoading} />

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

function RoadmapCard({ data, loading }: { data: RoadmapReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const sevTone = (s: string) => (s === "high" ? "danger" : s === "medium" ? "warning" : "neutral");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ListChecks className="h-4 w-4 text-blue-500" />
          {t("roadmap.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_items === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("roadmap.empty")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.items.map((item) => (
              <li
                key={item.signal}
                className="flex flex-col gap-1 rounded-md border border-[var(--border)] p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={sevTone(item.severity)}>
                    {t(`roadmap.severity.${item.severity}`)}
                  </Badge>
                  <span className="font-medium">{item.theme}</span>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {item.evidence} {t("roadmap.evidence")}
                  </span>
                </div>
                <p className="text-xs text-[var(--muted-foreground)]">{item.suggestion}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function InversionCard({ data, loading }: { data: InversionReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const pct = data?.recovery_rate != null ? Math.round(data.recovery_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Radar className="h-4 w-4 text-blue-500" />
          {t("inversion.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-12 w-full" />
        ) : !data?.available ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("inversion.unavailable")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("inversion.recoveryRate")}
                </span>
                <Badge tone={pct === 0 ? "success" : pct <= 33 ? "warning" : "danger"}>
                  {pct}%
                </Badge>
              </div>
              <Metric
                label={t("inversion.recoverable")}
                value={`${data.n_recoverable ?? 0}/${data.n_memories ?? 0}`}
              />
              <Metric label={t("inversion.threshold")} value={(data.threshold ?? 0).toFixed(2)} />
            </div>
            <ul className="flex flex-col gap-1.5 text-xs">
              {(data.matches ?? []).map((m, i) => (
                <li key={`${i}-${m.memory.slice(0, 12)}`} className="flex items-start gap-2">
                  <span
                    aria-hidden
                    className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                      m.recoverable ? "bg-red-500" : "bg-emerald-500"
                    }`}
                  />
                  <span className="min-w-0">
                    <span className={m.recoverable ? "text-red-600 dark:text-red-400" : ""}>
                      {m.memory}
                    </span>{" "}
                    <span className="text-[var(--muted-foreground)]">
                      ← “{m.probe}” ({m.cosine.toFixed(2)})
                    </span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-[var(--muted-foreground)]">{t("inversion.note")}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ErasureCoverageCard({
  data,
  loading,
}: {
  data: ErasureCoverage | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Eraser className="h-4 w-4 text-blue-500" />
          {t("erasure.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("erasure.conversations")} value={String(data.n_conversations)} />
              <Metric label={t("erasure.bundles")} value={String(data.n_bundles)} />
              <Metric label={t("erasure.scores")} value={String(data.n_scores)} />
            </div>
            <p className="text-xs text-[var(--muted-foreground)]">{t("erasure.note")}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MemoryInventoryCard({
  data,
  loading,
}: {
  data: InventoryReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const kinds = data ? Object.entries(data.by_kind) : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Archive className="h-4 w-4 text-blue-500" />
          {t("inventory.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_memories === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("inventory.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("inventory.memories")} value={String(data.n_memories)} />
              <Metric label={t("inventory.subjects")} value={String(data.n_subjects)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("inventory.expiringSoon")}
                </span>
                <Badge tone={data.n_expiring_soon === 0 ? "neutral" : "warning"}>
                  {data.n_expiring_soon}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {kinds.map(([kind, count]) => (
                  <Badge key={kind} tone="neutral">
                    {kind} · {count}
                  </Badge>
                ))}
              </div>
            </div>
            <ul className="flex flex-col gap-1 text-xs">
              {data.samples.map((s) => (
                <li key={s.memory_id} className="flex items-center gap-2">
                  <span className="font-mono text-[var(--muted-foreground)]">{s.subject}…</span>
                  <span className="min-w-0 flex-1 truncate">{s.preview}</span>
                  <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
                    {s.expires_in_days}d
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function JourneyCard({ data, loading }: { data: JourneyReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Footprints className="h-4 w-4 text-blue-500" />
          {t("journey.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_subjects === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("journey.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("journey.subjects")} value={String(data.n_subjects)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("journey.returning")}
                </span>
                <Badge tone={data.n_returning > 0 ? "success" : "neutral"}>
                  {data.n_returning}
                </Badge>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="py-2 pr-4 font-medium">{t("journey.subject")}</th>
                    <th className="py-2 pr-4 font-medium">{t("journey.sessions")}</th>
                    <th className="py-2 pr-4 font-medium">{t("journey.writes")}</th>
                    <th className="py-2 pr-4 font-medium">{t("journey.reads")}</th>
                    <th className="py-2 font-medium">{t("journey.span")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.subjects.slice(0, 8).map((j) => (
                    <tr key={j.subject} className="border-b border-[var(--border)]/50">
                      <td className="py-2 pr-4 font-mono text-xs">{j.subject}…</td>
                      <td className="py-2 pr-4 tabular-nums">
                        {j.returning ? <Badge tone="success">{j.n_sessions}</Badge> : j.n_sessions}
                      </td>
                      <td className="py-2 pr-4 tabular-nums">{j.n_writes}</td>
                      <td className="py-2 pr-4 tabular-nums">{j.n_reads}</td>
                      <td className="py-2 tabular-nums text-[var(--muted-foreground)]">
                        {j.span_days.toFixed(1)} d
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SftDatasetCard({ data, loading }: { data: SFTDataset | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const langs = data ? Object.entries(data.by_language) : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Sprout className="h-4 w-4 text-blue-500" />
          {t("sft.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_total === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("sft.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("sft.eligible")}</span>
                <Badge tone={data.n_eligible > 0 ? "success" : "neutral"}>
                  {data.n_eligible}/{data.n_total}
                </Badge>
              </div>
              <Metric label={t("sft.minScore")} value={data.min_score.toFixed(2)} />
              <div className="flex flex-wrap gap-2">
                {langs.map(([lang, count]) => (
                  <Badge key={lang} tone="neutral">
                    {lang} · {count}
                  </Badge>
                ))}
              </div>
            </div>
            {data.samples.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs text-[var(--muted-foreground)]">
                {data.samples.slice(0, 4).map((s, i) => (
                  <li key={`${i}-${s.output.slice(0, 12)}`} className="flex items-center gap-2">
                    <span className="uppercase">{s.language}</span>
                    <span className="tabular-nums">{s.score.toFixed(2)}</span>
                    <span className="min-w-0 truncate">{s.output}</span>
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

function AIActCard({ data, loading }: { data: AIActReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.compliance_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <BadgeCheck className="h-4 w-4 text-blue-500" />
          {t("aiAct.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("aiAct.compliance")}
                </span>
                <Badge tone={pct === 100 ? "success" : pct >= 80 ? "warning" : "danger"}>
                  {data.n_satisfied}/{data.n_obligations}
                </Badge>
              </div>
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("aiAct.riskClass")}
                </span>
                <Badge tone="neutral">{data.risk_class}</Badge>
              </div>
            </div>
            <ul className="flex flex-col gap-1 text-xs">
              {data.obligations.map((o) => (
                <li key={o.name} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      o.satisfied ? "bg-emerald-500" : "bg-red-500"
                    }`}
                  />
                  <span className="font-mono text-[0.65rem] text-[var(--muted-foreground)]">
                    {o.article}
                  </span>
                  <span className={o.satisfied ? "" : "text-red-600 dark:text-red-400"}>
                    {o.name}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PlaybooksCard({ data, loading }: { data: PlaybookReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const sevTone = (s: string) =>
    s === "critical" ? "danger" : s === "high" ? "warning" : "neutral";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Siren className="h-4 w-4 text-blue-500" />
          {t("playbooks.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_triggered === 0 ? (
          <p className="text-sm text-emerald-600 dark:text-emerald-400">{t("playbooks.clear")}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {data.playbooks.map((p) => (
              <li
                key={p.incident}
                className="flex flex-col gap-1.5 rounded-md border border-[var(--border)] p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={sevTone(p.severity)}>{t(`playbooks.severity.${p.severity}`)}</Badge>
                  <span className="font-medium">{p.incident}</span>
                  <span className="text-xs text-[var(--muted-foreground)]">{p.trigger}</span>
                </div>
                <ol className="ml-4 flex list-decimal flex-col gap-0.5 text-xs text-[var(--muted-foreground)]">
                  {p.steps.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ol>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function LocalizationCard({
  data,
  loading,
}: {
  data: LocalizationReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Globe className="h-4 w-4 text-blue-500" />
          {t("localization.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <Metric label={t("localization.keys")} value={String(data.n_default_keys)} />
            <div className="flex flex-wrap gap-6 text-sm">
              {data.locales.map((lc) => {
                const pct = Math.round(lc.completeness * 100);
                return (
                  <div key={lc.locale} className="flex flex-col gap-1">
                    <span className="text-xs text-[var(--muted-foreground)] uppercase">
                      {lc.locale}
                    </span>
                    <Badge tone={pct === 100 ? "success" : pct >= 90 ? "warning" : "danger"}>
                      {pct}%
                    </Badge>
                    {lc.n_missing > 0 ? (
                      <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                        −{lc.n_missing} {t("localization.missing")}
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>
            {data.locales.some((lc) => lc.missing_sample.length > 0) ? (
              <ul className="flex flex-col gap-0.5 font-mono text-[0.65rem] text-red-600 dark:text-red-400">
                {data.locales.flatMap((lc) =>
                  lc.missing_sample
                    .slice(0, 3)
                    .map((k) => <li key={`${lc.locale}-${k}`}>{`${lc.locale}: ${k}`}</li>),
                )}
              </ul>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SiemCard({ data, loading }: { data: SiemExport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const cats = data ? Object.entries(data.by_category) : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Radio className="h-4 w-4 text-blue-500" />
          {t("siem.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_events === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("siem.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("siem.events")} value={String(data.n_events)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("siem.high")}</span>
                <Badge tone={data.n_high_severity === 0 ? "success" : "danger"}>
                  {data.n_high_severity}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                {cats.map(([cat, n]) => (
                  <Badge key={cat} tone="neutral">
                    {cat} · {n}
                  </Badge>
                ))}
              </div>
            </div>
            <ul className="flex flex-col gap-1 font-mono text-xs">
              {data.events
                .slice(-5)
                .reverse()
                .map((e, i) => (
                  <li key={`${i}-${e.action}`} className="flex items-center gap-2">
                    <span
                      className={
                        e.severity >= 7
                          ? "text-red-600 dark:text-red-400"
                          : "text-[var(--muted-foreground)]"
                      }
                    >
                      [{e.severity}]
                    </span>
                    <span>{e.action}</span>
                    <span className="text-[var(--muted-foreground)]">{e.outcome}</span>
                    <span className="min-w-0 truncate text-[var(--muted-foreground)]">
                      {e.message}
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function LeastPrivilegeCard({
  data,
  loading,
}: {
  data: PrivilegeReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const utilPct = data ? Math.round(data.utilization_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <KeyRound className="h-4 w-4 text-blue-500" />
          {t("privilege.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("privilege.utilization")} value={`${utilPct}%`} />
              <Metric label={t("privilege.used")} value={`${data.n_used}/${data.n_granted}`} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("privilege.violations")}
                </span>
                <Badge tone={data.n_violations === 0 ? "success" : "danger"}>
                  {data.n_violations}
                </Badge>
              </div>
              {data.over_provisioned.length > 0 ? (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {t("privilege.overProvisioned")}
                  </span>
                  <span className="font-mono text-xs text-amber-600 dark:text-amber-400">
                    {data.over_provisioned.join(", ")}
                  </span>
                </div>
              ) : null}
            </div>
            {data.violations.length > 0 ? (
              <p className="font-mono text-xs text-red-600 dark:text-red-400">
                {data.violations.join(", ")}
              </p>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CrossTenantCard({
  data,
  loading,
}: {
  data: CrossTenantReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.leak_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Lock className="h-4 w-4 text-blue-500" />
          {t("crossTenant.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("crossTenant.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("crossTenant.rate")}
              </span>
              <Badge tone={pct === 0 ? "success" : "danger"}>{pct}%</Badge>
            </div>
            <Metric label={t("crossTenant.leaks")} value={`${data.n_leaks}/${data.n_turns}`} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ToxicityCard({ data, loading }: { data: ToxicityReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.toxicity_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Ban className="h-4 w-4 text-blue-500" />
          {t("toxicity.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("toxicity.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">{t("toxicity.rate")}</span>
                <Badge tone={pct === 0 ? "success" : "danger"}>{pct}%</Badge>
              </div>
              <Metric label={t("toxicity.flagged")} value={`${data.n_toxic}/${data.n_turns}`} />
            </div>
            {data.flagged.length > 0 ? (
              <ul className="flex flex-col gap-1 text-xs">
                {data.flagged.slice(0, 5).map((f, i) => (
                  <li key={`${i}-${f.question.slice(0, 12)}`} className="flex items-center gap-2">
                    <span className="font-mono text-red-600 dark:text-red-400">
                      {f.terms.join(", ")}
                    </span>
                    <span className="min-w-0 truncate text-[var(--muted-foreground)]">
                      {f.question}
                    </span>
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

function FailurePredictorCard({
  data,
  loading,
}: {
  data: PredictorEvaluation | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const precPct = data ? Math.round(data.precision * 100) : 0;
  const recallPct = data ? Math.round(data.recall * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Sparkles className="h-4 w-4 text-blue-500" />
          {t("predictor.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("predictor.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("predictor.precision")}
              </span>
              <Badge tone={precPct >= 70 ? "success" : precPct >= 40 ? "warning" : "danger"}>
                {precPct}%
              </Badge>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("predictor.recall")}
              </span>
              <Badge tone={recallPct >= 70 ? "success" : recallPct >= 40 ? "warning" : "danger"}>
                {recallPct}%
              </Badge>
            </div>
            <Metric label={t("predictor.predicted")} value={`${data.n_predicted_fail}/${data.n}`} />
            <Metric label={t("predictor.actual")} value={`${data.n_actual_fail}/${data.n}`} />
            <Metric
              label={t("predictor.confusion")}
              value={`${data.true_positive}·${data.false_positive}·${data.false_negative}`}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FailureClusterCard({
  data,
  loading,
}: {
  data: ClusterReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const purityPct = data?.mean_purity != null ? Math.round(data.mean_purity * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Grid3x3 className="h-4 w-4 text-blue-500" />
          {t("clusters.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-12 w-full" />
        ) : !data?.available ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("clusters.unavailable")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <Metric label={t("clusters.failures")} value={String(data.n_failures ?? 0)} />
              <Metric label={t("clusters.themes")} value={String(data.k ?? 0)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("clusters.purity")}
                </span>
                <Badge tone={purityPct >= 80 ? "success" : purityPct >= 60 ? "warning" : "danger"}>
                  {purityPct}%
                </Badge>
              </div>
            </div>
            <ul className="flex flex-col gap-2">
              {(data.clusters ?? []).map((c) => (
                <li
                  key={c.cluster_id}
                  className="flex flex-col gap-1 rounded-md border border-[var(--border)] p-2"
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge tone="neutral">{c.dominant_category}</Badge>
                    <span className="text-[var(--muted-foreground)]">
                      {c.size} {t("clusters.cases")} · {Math.round(c.purity * 100)}%
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 text-[0.65rem] text-[var(--muted-foreground)]">
                    {Object.entries(c.categories).map(([cat, n]) => (
                      <span key={cat} className="font-mono">
                        {cat}:{n}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function MemoryObsCard({ data, loading }: { data: MemoryObsReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const hitPct = data ? Math.round(data.recall_hit_rate * 100) : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Brain className="h-4 w-4 text-blue-500" />
          {t("memory.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_actions === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("memory.empty")}</p>
        ) : (
          <div className="flex flex-wrap items-end gap-6 text-sm">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">{t("memory.hitRate")}</span>
              <Badge tone={hitPct >= 50 ? "success" : "neutral"}>{hitPct}%</Badge>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-[var(--muted-foreground)]">
                {t("memory.injectionCaught")}
              </span>
              <Badge tone={data.items_screened_out === 0 ? "success" : "danger"}>
                {data.items_screened_out}
              </Badge>
            </div>
            <Metric label={t("memory.writes")} value={`${data.writes_allowed}/${data.n_writes}`} />
            <Metric label={t("memory.writesDenied")} value={String(data.writes_denied)} />
            <Metric label={t("memory.reads")} value={String(data.n_reads)} />
            <Metric label={t("memory.recalled")} value={String(data.items_recalled)} />
            <Metric label={t("memory.forgets")} value={String(data.n_forgets)} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CorpusFreshnessCard({
  data,
  loading,
}: {
  data: FreshnessReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <CalendarClock className="h-4 w-4 text-blue-500" />
          {t("freshness.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_corpora === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("freshness.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("freshness.stale")}
                </span>
                <Badge tone={data.n_stale === 0 ? "success" : "warning"}>
                  {data.n_stale}/{data.n_corpora}
                </Badge>
              </div>
              <Metric label={t("freshness.horizon")} value={`${data.max_age_days} d`} />
              <Metric label={t("freshness.oldest")} value={`${data.oldest_age_days} d`} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="py-2 pr-4 font-medium">{t("freshness.corpus")}</th>
                    <th className="py-2 pr-4 font-medium">{t("freshness.docs")}</th>
                    <th className="py-2 pr-4 font-medium">{t("freshness.age")}</th>
                    <th className="py-2 pr-4 font-medium">{t("freshness.asOf")}</th>
                    <th className="py-2 font-medium">{t("freshness.state")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.regulations.map((r) => (
                    <tr key={r.name} className="border-b border-[var(--border)]/50">
                      <td className="py-2 pr-4 uppercase">{r.corpus}</td>
                      <td className="py-2 pr-4 tabular-nums">{r.n_docs}</td>
                      <td className="py-2 pr-4 tabular-nums">{r.age_days} d</td>
                      <td className="py-2 pr-4 tabular-nums text-[var(--muted-foreground)]">
                        {r.as_of ?? "—"}
                      </td>
                      <td className="py-2">
                        <Badge tone={r.stale ? "warning" : "success"}>
                          {r.stale ? t("freshness.stateStale") : t("freshness.stateFresh")}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function EmbeddingSkewCard({ data, loading }: { data: SkewReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const tone =
    !data || data.severity === "none" ? "success" : data.severity === "soft" ? "warning" : "danger";
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Boxes className="h-4 w-4 text-blue-500" />
          {t("embeddingSkew.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("embeddingSkew.status")}
                </span>
                <Badge tone={tone}>{t(`embeddingSkew.severity.${data.severity}`)}</Badge>
              </div>
              <Metric
                label={t("embeddingSkew.query")}
                value={`${data.query_model} · ${data.query_dimension}d`}
              />
              <Metric
                label={t("embeddingSkew.corpus")}
                value={`${data.corpus_model} · ${data.corpus_dimension}d`}
              />
            </div>
            <p className="text-xs text-[var(--muted-foreground)]">{data.reason}</p>
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

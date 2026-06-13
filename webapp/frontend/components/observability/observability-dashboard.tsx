"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Archive,
  BadgeCheck,
  Ban,
  BookCheck,
  Boxes,
  Brain,
  CalendarClock,
  ChevronRight,
  Coins,
  Crosshair,
  Eraser,
  ExternalLink,
  FileDown,
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
  Megaphone,
  Microscope,
  Play,
  Radar,
  Radio,
  Receipt,
  Repeat,
  Route,
  Scale,
  Scissors,
  ShieldCheck,
  Siren,
  SlidersHorizontal,
  Sparkles,
  Sprout,
  Target,
  Undo2,
  Workflow,
  Wrench,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { ModelComparisonTable, RunsTable } from "@/components/observability/eval-runs";
import { EvolutionChart } from "@/components/observability/evolution-chart";
import { FailedCasesTable, FailureDistribution } from "@/components/observability/failed-cases";
import { JudgeCalibration } from "@/components/observability/judge-calibration";
import {
  CostQualityScatter,
  FaithGroundingScatter,
  OverviewKpis,
  RecommendedActions,
  RootCauseDiagnostic,
  RunsBars,
  TopProblems,
} from "@/components/observability/overview-exec";
import { ReplayPanel } from "@/components/observability/replay-panel";
import { SessionTheater } from "@/components/observability/session-theater";
import { SignalsTable, buildSignalRows } from "@/components/observability/signals-table";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchAIAct,
  fetchAnomalies,
  fetchCalibration,
  fetchCitationLinks,
  fetchCitations,
  fetchConformance,
  fetchContextOverflow,
  fetchContradictions,
  fetchCorpusFreshness,
  fetchCost,
  fetchCrossTenant,
  fetchDisclosure,
  fetchEmbeddingInversion,
  fetchEmbeddingSkew,
  fetchErasureCoverage,
  fetchEvalScores,
  fetchFailedCases,
  fetchFailureClusters,
  fetchFailurePredictor,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchGraphTopology,
  fetchGuardExplain,
  fetchGuardRetraction,
  fetchHandoffs,
  fetchIntent,
  fetchJudgeConsensus,
  fetchJudgeDrift,
  fetchLeastPrivilege,
  fetchLocaleFormat,
  fetchLocalization,
  fetchMemoryInventory,
  fetchMemoryObs,
  fetchMetricPairs,
  fetchModelComparison,
  fetchObsCost,
  fetchPiiLeak,
  fetchRedteam,
  fetchRefusal,
  fetchReleaseStatus,
  fetchReproducibility,
  fetchRouting,
  fetchRuns,
  fetchSLO,
  fetchScoreSeries,
  fetchSessions,
  fetchSftDataset,
  fetchSiem,
  fetchSpanPropagation,
  fetchTailSampling,
  fetchToolLoops,
  fetchToolValidity,
  fetchToxicity,
  fetchTraceSnapshot,
  fetchWhatChanged,
  runRedteam,
  runShadow,
} from "@/lib/api/client";
import type {
  AIActReport,
  AnomalyReport,
  Calibration,
  CitationResolution,
  CitationSummary,
  ClusterReport,
  ConformanceReport,
  ContradictionReport,
  CostReport,
  CrossTenantReport,
  DisclosureReport,
  ErasureCoverage,
  EvalScore,
  FailedCasesReport,
  FirewallEfficacy,
  FreshnessReport,
  GraphTopology,
  GuardExplainReport,
  HandoffReport,
  IntentReport,
  InventoryReport,
  InversionReport,
  LocaleFormatSummary,
  LocalizationReport,
  MemoryObsReport,
  ObsCostReport,
  OverflowReport,
  PIILeakSummary,
  PredictorEvaluation,
  PrivilegeReport,
  PropagationReport,
  RedTeamResponse,
  RefusalReport,
  ReleaseStatus,
  ReproReport,
  RetractionReport,
  RoutingReport,
  SFTDataset,
  SessionReport,
  ShadowReport,
  SiemExport,
  SkewReport,
  SnapshotDiffReport,
  TailSamplingReport,
  ToolLoopReport,
  ToolValidity,
  ToxicityReport,
  WhatChanged,
} from "@/lib/api/schemas";

// Locally-available Ollama models to shadow against (smallest first).
const SHADOW_MODELS = ["llama3.2:3b", "mistral:7b", "gemma3:27b", "llama3.3:70b"] as const;

const POLL_MS = 5_000;

// The Qualité IA page covers 42 of the 200-signal global catalogue (normative — see
// docs/ui-reference/qualite-ia-ui-reference/README.md). This is a coverage framing,
// not a live count, so it is a constant rather than a fabricated metric.
const QUALITY_SIGNALS = 42;
const QUALITY_CATALOGUE = 200;

const TAB_DEFS = ["overview", "signals", "runs", "failed", "models", "judge"] as const;
type TabKey = (typeof TAB_DEFS)[number];
const PHOENIX_URL = process.env.NEXT_PUBLIC_PHOENIX_URL ?? "http://localhost:16006";
const LANGFUSE_URL = process.env.NEXT_PUBLIC_LANGFUSE_URL ?? "http://localhost:3900";

function scoreTone(score: number): string {
  if (score >= 0.8) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 0.5) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function ObservabilityDashboard() {
  const t = useTranslations("observability");
  const tq = useTranslations("quality");
  const locale = useLocale();
  const [tab, setTab] = useState<TabKey>("overview");
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();

  const scores = useQuery({
    queryKey: ["eval-scores", asOf],
    queryFn: ({ signal }) => fetchEvalScores(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL_MS,
  });

  const slo = useQuery({
    queryKey: ["slo", asOf],
    queryFn: ({ signal }) => fetchSLO(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL_MS,
  });

  const tailSampling = useQuery({
    queryKey: ["tail-sampling"],
    queryFn: ({ signal }) => fetchTailSampling(signal),
    refetchInterval: 15_000,
  });

  // The span-propagation probe is stable per process and cached server-side.
  const spanPropagation = useQuery({
    queryKey: ["span-propagation"],
    queryFn: ({ signal }) => fetchSpanPropagation(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const scoreSeries = useQuery({
    queryKey: ["score-series", "faithfulness", asOf],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "faithfulness"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const groundingSeries = useQuery({
    queryKey: ["score-series", "grounding", asOf],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "grounding"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const metricPairs = useQuery({
    queryKey: ["metric-pairs", "faithfulness", "grounding", asOf],
    queryFn: ({ signal }) =>
      fetchMetricPairs(signal, "faithfulness", "grounding", asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const hallucinationSeries = useQuery({
    queryKey: ["score-series", "hallucination", asOf],
    queryFn: ({ signal }) => fetchScoreSeries(signal, asOf ?? undefined, "hallucination"),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  // Documented failure catalogue is static per locale (no polling, no as-of).
  const failedCases = useQuery({
    queryKey: ["failed-cases", locale],
    queryFn: ({ signal }) => fetchFailedCases(signal, locale),
    staleTime: Number.POSITIVE_INFINITY,
  });

  // Eval run archive — refreshes slowly; the report files change rarely.
  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: ({ signal }) => fetchRuns(signal),
    refetchInterval: 60_000,
  });

  const modelComparison = useQuery({
    queryKey: ["model-comparison"],
    queryFn: ({ signal }) => fetchModelComparison(signal),
    refetchInterval: 60_000,
  });

  const releaseStatus = useQuery({
    queryKey: ["release-status"],
    queryFn: ({ signal }) => fetchReleaseStatus(signal),
    refetchInterval: 60_000,
  });

  const reproducibility = useQuery({
    queryKey: ["reproducibility"],
    queryFn: ({ signal }) => fetchReproducibility(signal),
    refetchInterval: 20_000,
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
    queryKey: ["toxicity", asOf],
    queryFn: ({ signal }) => fetchToxicity(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
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
    queryKey: ["ai-act", asOf],
    queryFn: ({ signal }) => fetchAIAct(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  const citationLinks = useQuery({
    queryKey: ["citation-links"],
    queryFn: ({ signal }) => fetchCitationLinks(signal),
    refetchInterval: 15_000,
  });

  const disclosure = useQuery({
    queryKey: ["disclosure"],
    queryFn: ({ signal }) => fetchDisclosure(signal),
    staleTime: Number.POSITIVE_INFINITY,
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

  const judgeDrift = useQuery({
    queryKey: ["judge-drift", asOf],
    queryFn: ({ signal }) => fetchJudgeDrift(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Multi-judge consensus runs a panel of local judges server-side and is cached;
  // fetch once (it is slow and stable per process).
  const judgeConsensus = useQuery({
    queryKey: ["judge-consensus"],
    queryFn: ({ signal }) => fetchJudgeConsensus(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const firewall = useQuery({
    queryKey: ["firewall-efficacy"],
    queryFn: ({ signal }) => fetchFirewallEfficacy(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const tools = useQuery({
    queryKey: ["tool-validity", asOf],
    queryFn: ({ signal }) => fetchToolValidity(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const toolLoops = useQuery({
    queryKey: ["tool-loops"],
    queryFn: ({ signal }) => fetchToolLoops(signal),
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
    queryKey: ["pii-leak", asOf],
    queryFn: ({ signal }) => fetchPiiLeak(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const contradictions = useQuery({
    queryKey: ["contradictions"],
    queryFn: ({ signal }) => fetchContradictions(signal),
    refetchInterval: 20_000,
  });

  const whatChanged = useQuery({
    queryKey: ["what-changed", asOf],
    queryFn: ({ signal }) => fetchWhatChanged(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 20_000,
  });

  const anomalies = useQuery({
    queryKey: ["anomalies", asOf],
    queryFn: ({ signal }) => fetchAnomalies(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 20_000,
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
    queryKey: ["conformance", asOf],
    queryFn: ({ signal }) => fetchConformance(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const intent = useQuery({
    queryKey: ["intent"],
    queryFn: ({ signal }) => fetchIntent(signal),
    refetchInterval: 15_000,
  });

  const cost = useQuery({
    queryKey: ["cost", asOf],
    queryFn: ({ signal }) => fetchCost(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  const contextOverflow = useQuery({
    queryKey: ["context-overflow"],
    queryFn: ({ signal }) => fetchContextOverflow(signal),
    refetchInterval: 15_000,
  });

  const guardExplain = useQuery({
    queryKey: ["guard-explain"],
    queryFn: ({ signal }) => fetchGuardExplain(signal),
    refetchInterval: 15_000,
  });

  const guardRetraction = useQuery({
    queryKey: ["guard-retraction"],
    queryFn: ({ signal }) => fetchGuardRetraction(signal),
    refetchInterval: 15_000,
  });

  // Graph topology is stable per process unless the deploy reshapes the graph.
  const graphTopology = useQuery({
    queryKey: ["graph-topology"],
    queryFn: ({ signal }) => fetchGraphTopology(signal),
    staleTime: Number.POSITIVE_INFINITY,
  });

  const traceSnapshot = useQuery({
    queryKey: ["trace-snapshot"],
    queryFn: ({ signal }) => fetchTraceSnapshot(signal),
    refetchInterval: 20_000,
  });

  const handoffs = useQuery({
    queryKey: ["handoffs"],
    queryFn: ({ signal }) => fetchHandoffs(signal),
    refetchInterval: 20_000,
  });

  const funnel = useQuery({
    queryKey: ["funnel", asOf],
    queryFn: ({ signal }) => fetchFunnel(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  // Newest first for display.
  const rows: EvalScore[] = scores.data ? [...scores.data.scores].reverse() : [];

  // Unified signal catalogue derived from the live reports (reference image 01).
  const signalRows = buildSignalRows(t, {
    slo: slo.data,
    calibration: calibration.data,
    citations: citations.data,
    contradiction: contradictions.data,
    predictor: failurePredictor.data,
    clusters: failureClusters.data,
    firewall: firewall.data,
    toxicity: toxicity.data,
    pii: piiLeak.data,
    refusal: refusal.data,
    conformance: conformance.data,
    localeFormat: localeFormat.data,
    tools: tools.data,
    cost: cost.data,
    routing: routing.data,
    funnel: funnel.data,
    anomalies: anomalies.data,
    intent: intent.data,
  });

  // --- Real derived headline metrics (no fabrication — null ⇒ "—") -----------
  const sloPct = slo.data && slo.data.n > 0 ? Math.round(slo.data.good_rate * 100) : null;
  const topFailing = failureClusters.data?.available
    ? [...(failureClusters.data.clusters ?? [])].sort((a, b) => b.size - a.size).slice(0, 4)
    : [];

  function downloadQualityEvidence() {
    const bundle = {
      generated_at: new Date().toISOString(),
      page: "quality",
      window: tq("temporal.window"),
      signals_covered: `${QUALITY_SIGNALS}/${QUALITY_CATALOGUE}`,
      slo: slo.data ?? null,
      refusal: refusal.data ?? null,
      conformance: conformance.data ?? null,
      calibration: calibration.data ?? null,
      toxicity: toxicity.data ?? null,
      pii_leak: piiLeak.data ?? null,
      ai_act: aiAct.data ?? null,
      failure_clusters: failureClusters.data ?? null,
    };
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tessera-quality-evidence-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Sticky chrome: tab bar + business actions on one row (image normative),
          the shared compact temporal rail (Live/Replay) below. */}
      <div className="sticky top-0 z-30 -mx-3 flex flex-col gap-2 bg-[var(--tessera-bg)] px-3 pb-2 pt-2 shadow-[0_-16px_0_0_var(--tessera-bg)]">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <TabBar active={tab} onChange={setTab} />
          <div className="flex shrink-0 items-center gap-2">
            <Button
              size="sm"
              onClick={() => setTab("runs")}
              className="h-9 gap-2 border border-[#007a55] bg-[#005c42] text-xs text-[#d6f0e3] hover:bg-[#006d4e]"
            >
              <Play className="h-3.5 w-3.5" />
              {tq("cta.runEval")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTab("models")}
              className="h-9 gap-2 text-xs"
            >
              <GitCompareArrows className="h-3.5 w-3.5" />
              {tq("cta.compareModels")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTab("runs")}
              className="h-9 gap-2 text-xs"
            >
              <Boxes className="h-3.5 w-3.5" />
              {tq("cta.openDataset")}
            </Button>
            <Button size="sm" onClick={downloadQualityEvidence} className="h-9 gap-2 text-xs">
              <FileDown className="h-3.5 w-3.5" />
              {tq("cta.evidence")}
            </Button>
          </div>
        </div>
        <TemporalRail
          mode={temporal.mode}
          liveStatus={tq("temporal.liveData")}
          timeline={railTimeline.data}
          sloTarget={slo.data?.target}
          selectedAt={temporal.selectedAt}
          onSelectedAtChange={temporal.setSelectedAt}
          periodKey={temporal.periodKey}
          onPeriodChange={temporal.setPeriodKey}
          onModeChange={temporal.changeMode}
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-3">
          {tab === "overview" && (
            <>
              {/* A. État actuel — KPI métriques compacts (image normative) */}
              <SectionLabel>{tq("sec.etat")}</SectionLabel>
              <OverviewKpis
                sloPct={sloPct}
                faithfulness={scoreSeries.data}
                grounding={groundingSeries.data}
                hallucination={hallucinationSeries.data}
                nonRegression={releaseStatus.data?.non_regression_rate ?? null}
                nRegressions={releaseStatus.data?.n_regressions ?? null}
                kappa={calibration.data?.kappa ?? null}
                casEvalues={scoreSeries.data?.n ?? null}
                loading={scoreSeries.isLoading}
              />

              {/* B. Diagnostic racine — Clusters | Ce qui a changé | Calibration | Exemples.
                  No items-start ⇒ all cards stretch to the row's tallest (equal heights). */}
              <SectionLabel>{tq("sec.diagnostic")}</SectionLabel>
              <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
                <FailureDistribution report={failedCases.data} loading={failedCases.isLoading} />
                <RootCauseDiagnostic
                  whatChanged={whatChanged.data}
                  regressions={releaseStatus.data?.regressions ?? []}
                />
                <CalibrationCard data={calibration.data} loading={calibration.isLoading} />
                <FailedCasesTable
                  report={failedCases.data}
                  loading={failedCases.isLoading}
                  limit={4}
                />
              </div>

              {/* C. Signaux prédictifs — Prédicteur | Intents | Langues (Évolution moves to
                  the full-width analytics row below the grid). */}
              <SectionLabel>{tq("sec.predictive")}</SectionLabel>
              <div className="grid gap-3 lg:grid-cols-3">
                <FailurePredictorCard
                  data={failurePredictor.data}
                  loading={failurePredictor.isLoading}
                />
                <IntentCard data={intent.data} loading={intent.isLoading} />
                <LocalizationCard data={localization.data} loading={localization.isLoading} />
              </div>

              {/* D. Actions recommandées — actions gouvernées (rôle + lien), pas de charts */}
              <SectionLabel>{tq("sec.actions")}</SectionLabel>
              <div className="grid gap-3 lg:grid-cols-2">
                <RecommendedActions
                  regressions={releaseStatus.data?.regressions ?? []}
                  topFailing={topFailing}
                  failed={failedCases.data}
                  onOpen={setTab}
                />
                <TopProblems rows={signalRows} />
              </div>
            </>
          )}

          {tab === "signals" && (
            <TabGrid>
              <FullWidth>
                <SignalsTable rows={signalRows} />
              </FullWidth>
              <CitationCard data={citations.data} loading={citations.isLoading} />
              <CitationLinksCard data={citationLinks.data} loading={citationLinks.isLoading} />
              <ContradictionCard data={contradictions.data} loading={contradictions.isLoading} />
              <CalibrationCard data={calibration.data} loading={calibration.isLoading} />
              <FirewallEfficacyCard data={firewall.data} loading={firewall.isLoading} />
              <RedTeamCard />
              <ToxicityCard data={toxicity.data} loading={toxicity.isLoading} />
              <PiiLeakCard data={piiLeak.data} loading={piiLeak.isLoading} />
              <CrossTenantCard data={crossTenant.data} loading={crossTenant.isLoading} />
              <LeastPrivilegeCard data={leastPrivilege.data} loading={leastPrivilege.isLoading} />
              <GuardRetractionCard
                data={guardRetraction.data}
                loading={guardRetraction.isLoading}
              />
              <GuardExplainCard data={guardExplain.data} loading={guardExplain.isLoading} />
              <InversionCard
                data={embeddingInversion.data}
                loading={embeddingInversion.isLoading}
              />
              <FullWidth>
                <SiemCard data={siem.data} loading={siem.isLoading} />
              </FullWidth>
              <AIActCard data={aiAct.data} loading={aiAct.isLoading} />
              <DisclosureCard data={disclosure.data} loading={disclosure.isLoading} />
              <LocalizationCard data={localization.data} loading={localization.isLoading} />
              <LocaleFormatCard data={localeFormat.data} loading={localeFormat.isLoading} />
              <RefusalCard data={refusal.data} loading={refusal.isLoading} />
              <ConformanceCard data={conformance.data} loading={conformance.isLoading} />
              <CostCard data={cost.data} loading={cost.isLoading} />
              <ObsCostCard data={obsCost.data} loading={obsCost.isLoading} />
              <ContextOverflowCard
                data={contextOverflow.data}
                loading={contextOverflow.isLoading}
              />
              <TailSamplingCard data={tailSampling.data} loading={tailSampling.isLoading} />
              <SpanPropagationCard
                data={spanPropagation.data}
                loading={spanPropagation.isLoading}
              />
              <ReproducibilityCard
                data={reproducibility.data}
                loading={reproducibility.isLoading}
              />
              <GraphTopologyCard data={graphTopology.data} loading={graphTopology.isLoading} />
              <TraceSnapshotCard data={traceSnapshot.data} loading={traceSnapshot.isLoading} />
              <HandoffsCard data={handoffs.data} loading={handoffs.isLoading} />
              <ToolLoopsCard data={toolLoops.data} loading={toolLoops.isLoading} />
              <ToolValidityCard data={tools.data} loading={tools.isLoading} />
              <RoutingCard data={routing.data} loading={routing.isLoading} />
              <IntentCard data={intent.data} loading={intent.isLoading} />
              <SessionCard data={sessions.data} loading={sessions.isLoading} />
              <AnomalyCard data={anomalies.data} loading={anomalies.isLoading} />
              <MemoryObsCard data={memoryObs.data} loading={memoryObs.isLoading} />
              <MemoryInventoryCard
                data={memoryInventory.data}
                loading={memoryInventory.isLoading}
              />
              <ErasureCoverageCard
                data={erasureCoverage.data}
                loading={erasureCoverage.isLoading}
              />
              <EmbeddingSkewCard data={embeddingSkew.data} loading={embeddingSkew.isLoading} />
              <CorpusFreshnessCard
                data={corpusFreshness.data}
                loading={corpusFreshness.isLoading}
              />
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
            </TabGrid>
          )}

          {tab === "runs" && (
            <TabGrid>
              <FullWidth>
                <RunsTable registry={runs.data} loading={runs.isLoading} />
              </FullWidth>
              <FullWidth>
                <ScoresTable rows={rows} loading={scores.isLoading} />
              </FullWidth>
              <SftDatasetCard data={sftDataset.data} loading={sftDataset.isLoading} />
              <CostCard data={cost.data} loading={cost.isLoading} />
              <ObsCostCard data={obsCost.data} loading={obsCost.isLoading} />
              <ReproducibilityCard
                data={reproducibility.data}
                loading={reproducibility.isLoading}
              />
              <FullWidth>
                <SessionTheater />
              </FullWidth>
              <FullWidth>
                <ReplayPanel />
              </FullWidth>
            </TabGrid>
          )}

          {tab === "failed" && (
            <TabGrid>
              <FullWidth>
                <FailedCasesTable report={failedCases.data} loading={failedCases.isLoading} />
              </FullWidth>
              <FailureDistribution report={failedCases.data} loading={failedCases.isLoading} />
              <FailureClusterCard data={failureClusters.data} loading={failureClusters.isLoading} />
              <FailurePredictorCard
                data={failurePredictor.data}
                loading={failurePredictor.isLoading}
              />
              <ContradictionCard data={contradictions.data} loading={contradictions.isLoading} />
              <ToxicityCard data={toxicity.data} loading={toxicity.isLoading} />
              <PiiLeakCard data={piiLeak.data} loading={piiLeak.isLoading} />
            </TabGrid>
          )}

          {tab === "models" && (
            <TabGrid>
              <FullWidth>
                <ModelComparisonTable
                  data={modelComparison.data}
                  loading={modelComparison.isLoading}
                />
              </FullWidth>
              <FullWidth>
                <ShadowCard />
              </FullWidth>
              <CalibrationCard data={calibration.data} loading={calibration.isLoading} />
            </TabGrid>
          )}

          {tab === "judge" && (
            <JudgeCalibration
              data={calibration.data}
              drift={judgeDrift.data}
              consensus={judgeConsensus.data}
              loading={calibration.isLoading}
            />
          )}
        </div>

        <RightRail
          failed={failedCases.data}
          release={releaseStatus.data}
          whatChanged={whatChanged.data}
          onOpen={setTab}
        />
      </div>

      {/* Full-width analytics row below the [main · rail] grid (image normative):
          Évolution de la qualité | Faith×Grounding | Pass-rate des runs | Coût vs qualité.
          Spanning the whole width lets the right rail's last card align with D above. */}
      {tab === "overview" ? (
        <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
          <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
          <FaithGroundingScatter pairs={metricPairs.data} loading={metricPairs.isLoading} />
          <RunsBars registry={runs.data} loading={runs.isLoading} />
          <CostQualityScatter data={modelComparison.data} loading={modelComparison.isLoading} />
        </div>
      ) : null}

      <StatusBar release={releaseStatus.data} />
    </div>
  );
}

/** Compact section heading (A. / B. / C. / D.) above each overview row. */
function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <h2 className="mt-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
      {children}
    </h2>
  );
}

/** Thin sticky status bar pinned to the bottom of the page (image normative). */
function StatusBar({ release }: { release: ReleaseStatus | undefined }) {
  const tq = useTranslations("quality");
  const dataset = release?.current ? `Llama · ${release.current.version}` : "—";
  const updated = release?.current?.date ?? "—";
  const items = [
    { icon: Radio, label: tq("statusbar.realtime"), tone: "text-[var(--tessera-green)]" },
    { icon: Boxes, label: `${tq("statusbar.dataset")} : ${dataset}` },
    { icon: ShieldCheck, label: tq("statusbar.truthChain") },
    { icon: Landmark, label: tq("statusbar.truthSource") },
    { icon: CalendarClock, label: `${tq("statusbar.lastUpdate")} : ${updated}` },
    { icon: ListChecks, label: tq("statusbar.signals", { n: QUALITY_SIGNALS }) },
  ];
  return (
    <div className="sticky bottom-0 z-20 -mx-3 flex h-9 items-center gap-4 overflow-hidden border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-[0.7rem] text-[var(--tessera-text-muted)]">
      {items.map((it) => (
        <span key={it.label} className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
          <it.icon className={`h-3.5 w-3.5 shrink-0 ${it.tone ?? ""}`} />
          <span className="truncate">{it.label}</span>
        </span>
      ))}
      <span className="ml-auto flex shrink-0 items-center gap-1.5 whitespace-nowrap text-[var(--tessera-green)]">
        <span className="h-2 w-2 rounded-full bg-[var(--tessera-green)]" />
        {tq("statusbar.systemOk")}
      </span>
    </div>
  );
}

const TAB_META: Record<TabKey, typeof Gauge> = {
  overview: Gauge,
  signals: ListChecks,
  runs: Boxes,
  failed: Siren,
  models: GitCompareArrows,
  judge: Scale,
};

function TabBar({ active, onChange }: { active: TabKey; onChange: (tab: TabKey) => void }) {
  const tq = useTranslations("quality");
  return (
    <nav className="flex min-w-0 items-center gap-1 overflow-x-auto border-b border-[var(--tessera-border)]">
      {TAB_DEFS.map((key) => {
        const Icon = TAB_META[key];
        const on = key === active;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[0.8rem] transition-colors ${
              on
                ? "border-[var(--tessera-green)] font-medium text-[var(--tessera-text)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Icon className="h-4 w-4" />
            {tq(`tabs.${key}`)}
          </button>
        );
      })}
    </nav>
  );
}

/** Responsive two-column signal grid. FullWidth spans both columns. */
function TabGrid({ children }: { children: ReactNode }) {
  return <div className="grid items-start gap-4 lg:grid-cols-2">{children}</div>;
}

/** Persistent right rail: score summary, top failing categories, sensitive actions, evidence. */
const SEV_TONE: Record<string, "danger" | "warning" | "neutral"> = {
  critical: "danger",
  high: "warning",
  medium: "neutral",
  low: "neutral",
};

/** Right rail (image normative): Derniers problèmes · Release actuelle · Liens
 * rapides · Activités récentes — all fed by live data, links into the tabs. */
function RightRail({
  failed,
  release,
  whatChanged,
  onOpen,
}: {
  failed: FailedCasesReport | undefined;
  release: ReleaseStatus | undefined;
  whatChanged: WhatChanged | undefined;
  onOpen: (tab: TabKey) => void;
}) {
  const tq = useTranslations("quality");
  const current = release?.current ?? null;
  const nReg = release?.n_regressions ?? 0;
  const problems = (failed?.cases ?? []).slice(0, 3);
  const quick: { label: string; icon: typeof Activity; tab: TabKey }[] = [
    { label: tq("rr.quickRun"), icon: Activity, tab: "runs" },
    { label: tq("rr.quickPolicies"), icon: ShieldCheck, tab: "signals" },
    { label: tq("rr.quickScheduled"), icon: CalendarClock, tab: "runs" },
    { label: tq("rr.quickCatalog"), icon: ListChecks, tab: "signals" },
  ];
  // Recent activity, derived from the real "what changed" diff + the release.
  const activity: { key: string; label: string; detail: string }[] = [];
  if (current) {
    activity.push({
      key: "release",
      label: `${current.version} · ${tq("rr.since")}`,
      detail: current.date ?? "",
    });
  }
  for (const c of whatChanged?.changes ?? []) {
    activity.push({
      key: c.field,
      label: c.field,
      detail: `${c.before.slice(0, 8)} → ${c.after.slice(0, 8)}`,
    });
  }

  return (
    <aside className="flex min-w-0 flex-col gap-3">
      <div className="flex flex-col gap-3 xl:sticky xl:top-28">
        {/* Derniers problèmes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.problems")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {problems.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("rr.noProblems")}</p>
            ) : (
              problems.map((p) => (
                <div key={p.case_id} className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-col">
                    <span className="truncate text-sm">{p.title}</span>
                    <span className="truncate text-[0.7rem] text-[var(--muted-foreground)]">
                      {p.category}
                    </span>
                  </div>
                  <Badge tone={SEV_TONE[p.severity] ?? "neutral"}>{p.severity}</Badge>
                </div>
              ))
            )}
            <RailLink onClick={() => onOpen("failed")}>{tq("rr.seeCases")}</RailLink>
          </CardContent>
        </Card>

        {/* Release actuelle */}
        {current ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-2 text-sm">
                {tq("rr.release")}
                <Badge tone={nReg === 0 ? "success" : "warning"}>{tq("rr.inProd")}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              <div className="flex items-end gap-2">
                <span className="font-serif text-xl font-semibold tabular-nums">
                  {current.version}
                </span>
                {current.date ? (
                  <span className="pb-1 text-xs text-[var(--muted-foreground)]">
                    {current.date}
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-[var(--muted-foreground)]">
                {tq("release.changes", { n: current.added + current.changed + current.fixed })}
                {release && release.models_compared > 0
                  ? ` · ${Math.round(release.non_regression_rate * 100)}%`
                  : ""}
              </p>
              <RailLink onClick={() => onOpen("models")}>{tq("rr.seeReleases")}</RailLink>
            </CardContent>
          </Card>
        ) : null}

        {/* Liens rapides */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.quick")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            {quick.map((q) => (
              <button
                key={q.label}
                type="button"
                onClick={() => onOpen(q.tab)}
                className="flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-sm transition-colors hover:bg-[var(--tessera-muted)]"
              >
                <q.icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
                <span className="truncate">{q.label}</span>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Activités récentes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.activity")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {activity.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("rr.noActivity")}</p>
            ) : (
              activity.slice(0, 4).map((a) => (
                <div key={a.key} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tessera-green)]" />
                  <span className="min-w-0 flex-1 truncate text-sm">{a.label}</span>
                  <span className="shrink-0 font-mono text-[0.65rem] text-[var(--muted-foreground)]">
                    {a.detail}
                  </span>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </aside>
  );
}

/** Small "see all →" link used at the foot of a right-rail card. */
function RailLink({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-1 inline-flex items-center gap-1 text-xs text-[var(--tessera-green)] hover:underline"
    >
      {children}
      <ChevronRight className="h-3 w-3" />
    </button>
  );
}

/** Recent eval scores table — reused on Overview and Runs & datasets. */
function ScoresTable({ rows, loading }: { rows: EvalScore[]; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          {t("scores.title")}
          <Badge tone="neutral">{t("scores.metric")}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
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
  );
}

/** Span both columns of a section grid (for wide tables / panels). */
function FullWidth({ children }: { children: ReactNode }) {
  return <div className="lg:col-span-2">{children}</div>;
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

function DisclosureCard({
  data,
  loading,
}: {
  data: DisclosureReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const locale = useLocale();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Megaphone className="h-4 w-4 text-blue-500" />
          {t("disclosure.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge tone={data.enabled && data.all_covered ? "success" : "danger"}>
                {data.enabled ? t("disclosure.active") : t("disclosure.off")}
              </Badge>
              <span className="font-mono text-xs text-[var(--muted-foreground)]">
                {data.article}
              </span>
              <Metric label={t("disclosure.locales")} value={String(data.n_locales)} />
            </div>
            <p className="rounded-md bg-[var(--muted)]/40 p-3 text-xs italic">
              “{data.texts[locale] ?? data.texts.en}”
            </p>
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

// Open speedometer gauge (the normative "arc"): a ~240° sweep, wider than a
// semicircle, with the endpoints angled downward. Tuned to the 100×72 viewBox.
const _GAUGE_SWEEP = 240; // degrees
const _GAUGE_CX = 50;
const _GAUGE_CY = 44;
const _GAUGE_R = 38;

/** Point on the gauge arc at fraction ``t`` (0 = left end, 1 = right end). */
function gaugePoint(t: number): [number, number] {
  const half = _GAUGE_SWEEP / 2;
  const deg = 90 + half - t * _GAUGE_SWEEP; // left (210°) → top (90°) → right (-30°)
  const a = (deg * Math.PI) / 180;
  return [_GAUGE_CX + _GAUGE_R * Math.cos(a), _GAUGE_CY - _GAUGE_R * Math.sin(a)];
}

/** Open agreement gauge: a >180° arc whose green fill reaches κ over a grey
 * track, value centred — the normative "Calibration du juge" arc. */
function OpenGauge({ value, color }: { value: number; color: string }) {
  const f = Math.max(0, Math.min(1, value));
  const [lx, ly] = gaugePoint(0);
  const [rx, ry] = gaugePoint(1);
  const [ex, ey] = gaugePoint(f);
  const large = _GAUGE_SWEEP > 180 ? 1 : 0; // track is the major arc
  const fillLarge = f * _GAUGE_SWEEP > 180 ? 1 : 0;
  const track = `M ${lx.toFixed(2)} ${ly.toFixed(2)} A ${_GAUGE_R} ${_GAUGE_R} 0 ${large} 1 ${rx.toFixed(2)} ${ry.toFixed(2)}`;
  const fill = `M ${lx.toFixed(2)} ${ly.toFixed(2)} A ${_GAUGE_R} ${_GAUGE_R} 0 ${fillLarge} 1 ${ex.toFixed(2)} ${ey.toFixed(2)}`;
  return (
    <div className="relative h-[92px] w-[160px]">
      <svg viewBox="0 0 100 72" className="h-full w-full" aria-hidden="true">
        <path
          d={track}
          fill="none"
          stroke="var(--tessera-border)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {f > 0 ? (
          <path d={fill} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" />
        ) : null}
      </svg>
      <div className="absolute inset-x-0 top-[42%] flex flex-col items-center">
        <span
          className="font-serif text-2xl font-semibold leading-none tabular-nums"
          style={{ color }}
        >
          {value.toFixed(2)}
        </span>
        <span className="mt-0.5 text-[0.6rem] text-[var(--muted-foreground)]">κ</span>
      </div>
    </div>
  );
}

function CalibrationCard({ data, loading }: { data: Calibration | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const kappa = data?.kappa ?? 0;
  const good = kappa >= 0.6;
  const color = kappa >= 0.8 ? "#10b981" : kappa >= 0.6 ? "#f59e0b" : "#ef4444";
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
          <div className="flex flex-col items-center gap-1">
            <OpenGauge value={kappa} color={color} />
            <div className="-mt-2 flex w-[160px] items-center justify-between text-[0.7rem] text-[var(--muted-foreground)]">
              <span>0</span>
              <span className="truncate px-1 text-center">{t("calibration.interJudge")}</span>
              <span>1</span>
            </div>
            <Badge tone={good ? "success" : "warning"} className="mt-1">
              {good ? t("calibration.verdictGood") : t("calibration.verdictBad")}
            </Badge>
            <div className="mt-2 grid w-full grid-cols-2 gap-x-4 gap-y-1.5 border-t border-[var(--tessera-border)] pt-2 text-xs">
              <Metric
                label={t("calibration.agreement")}
                value={`${Math.round((data.agreement ?? 0) * 100)}%`}
              />
              <Metric
                label={t("calibration.verbosity")}
                value={(data.verbosity_corr ?? 0).toFixed(2)}
              />
              <Metric label={t("calibration.samples")} value={String(data.n ?? 0)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("calibration.lenient")}
                </span>
                <Badge tone={data.lenient ? "warning" : "success"}>
                  {data.lenient ? t("calibration.lenientYes") : t("calibration.lenientNo")}
                </Badge>
              </div>
              <div className="col-span-2 flex items-center justify-between gap-2">
                <span className="text-[var(--muted-foreground)]">{t("calibration.judge")}</span>
                <span className="truncate font-mono text-[0.7rem]">{data.judge_model ?? "—"}</span>
              </div>
            </div>
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

function CitationLinksCard({
  data,
  loading,
}: {
  data: CitationResolution | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const pct = data ? Math.round(data.resolvable_rate * 100) : 100;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <BookCheck className="h-4 w-4 text-blue-500" />
          {t("citationLinks.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_citations === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("citationLinks.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("citationLinks.resolvable")}
                </span>
                <Badge tone={pct === 100 ? "success" : pct >= 70 ? "warning" : "danger"}>
                  {pct}%
                </Badge>
              </div>
              <Metric
                label={t("citationLinks.resolved")}
                value={`${data.n_resolved}/${data.n_citations}`}
              />
            </div>
            <ul className="flex flex-col gap-1 text-xs">
              {data.links.slice(0, 6).map((l, i) => (
                <li key={`${i}-${l.citation.slice(0, 16)}`} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      l.resolved ? "bg-emerald-500" : "bg-red-500"
                    }`}
                  />
                  {l.source ? (
                    <span className="font-mono text-[var(--muted-foreground)]">{l.source}</span>
                  ) : (
                    <span className="text-red-600 dark:text-red-400">
                      {t("citationLinks.dangling")}
                    </span>
                  )}
                  <span className="min-w-0 truncate text-[var(--muted-foreground)]">
                    {l.citation}
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

function ContextOverflowCard({
  data,
  loading,
}: {
  data: OverflowReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  const overflowed = data?.turns.filter((x) => x.overflowed) ?? [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Scissors className="h-4 w-4 text-blue-500" />
          {t("overflow.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("overflow.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("overflow.overflowed")}
                </span>
                <Badge tone={data.n_overflowed === 0 ? "success" : "danger"}>
                  {data.n_overflowed}/{data.n_turns}
                </Badge>
              </div>
              <Metric label={t("overflow.window")} value={`${data.usable_tokens} tok`} />
              <Metric label={t("overflow.peak")} value={`${data.max_context_tokens} tok`} />
            </div>
            {overflowed.length === 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {t("overflow.clear")}
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {overflowed.slice(0, 5).map((x, i) => (
                  <li key={`${i}-${x.question.slice(0, 12)}`} className="flex items-center gap-2">
                    <Badge tone="danger">−{x.n_dropped}</Badge>
                    <span className="tabular-nums text-[var(--muted-foreground)]">
                      {x.context_tokens} tok
                    </span>
                    <span className="min-w-0 truncate">{x.question}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ToolLoopsCard({ data, loading }: { data: ToolLoopReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Repeat className="h-4 w-4 text-blue-500" />
          {t("toolLoops.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_calls === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("toolLoops.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("toolLoops.loops")}
                </span>
                <Badge tone={data.n_loops === 0 ? "success" : "danger"}>{data.n_loops}</Badge>
              </div>
              <Metric label={t("toolLoops.calls")} value={String(data.n_calls)} />
              <Metric label={t("toolLoops.threshold")} value={`≥${data.repeat_threshold}`} />
            </div>
            {data.n_loops === 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {t("toolLoops.clear")}
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {data.loops.map((l, i) => (
                  <li key={`${i}-${l.tools.join("-")}`} className="flex items-center gap-2">
                    <Badge tone="danger">{t(`toolLoops.${l.kind}`)}</Badge>
                    <span className="font-mono">{l.tools.join(" ↔ ")}</span>
                    <span className="text-[var(--muted-foreground)]">×{l.length}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ReproducibilityCard({
  data,
  loading,
}: {
  data: ReproReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Hash className="h-4 w-4 text-blue-500" />
          {t("repro.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("repro.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("repro.nondeterministic")}
                </span>
                <Badge tone={data.n_nondeterministic === 0 ? "success" : "danger"}>
                  {data.n_nondeterministic}
                </Badge>
              </div>
              <Metric label={t("repro.turns")} value={String(data.n_turns)} />
              <Metric label={t("repro.repeated")} value={String(data.n_repeated_inputs)} />
            </div>
            {data.n_nondeterministic === 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">{t("repro.clear")}</p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {data.divergences.slice(0, 5).map((d, i) => (
                  <li key={`${i}-${d.question.slice(0, 12)}`} className="flex items-center gap-2">
                    <Badge tone="danger">×{d.n_variants}</Badge>
                    <span className="min-w-0 truncate">{d.question}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-[var(--muted-foreground)]">{t("repro.note")}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SpanPropagationCard({
  data,
  loading,
}: {
  data: PropagationReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Workflow className="h-4 w-4 text-blue-500" />
          {t("propagation.title")}
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
                  {t("propagation.status")}
                </span>
                <Badge tone={data.propagated_ok ? "success" : "danger"}>
                  {data.propagated_ok ? t("propagation.ok") : t("propagation.broken")}
                </Badge>
              </div>
              <Metric label={t("propagation.spans")} value={String(data.n_spans)} />
              <Metric label={t("propagation.fanout")} value={String(data.max_fanout)} />
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("propagation.orphans")}
                </span>
                <Badge tone={data.n_orphans === 0 ? "success" : "danger"}>{data.n_orphans}</Badge>
              </div>
            </div>
            <p className="text-xs text-[var(--muted-foreground)]">{t("propagation.note")}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GuardRetractionCard({
  data,
  loading,
}: {
  data: RetractionReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Undo2 className="h-4 w-4 text-blue-500" />
          {t("retraction.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_answers === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("retraction.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("retraction.retractions")}
                </span>
                <Badge tone={data.n_retractions === 0 ? "success" : "danger"}>
                  {data.n_retractions}/{data.n_answers}
                </Badge>
              </div>
              <Metric label={t("retraction.maxExposed")} value={`${data.max_tokens_exposed} tok`} />
              <Metric
                label={t("retraction.meanExposed")}
                value={`${data.mean_tokens_exposed.toFixed(1)} tok`}
              />
            </div>
            {data.n_retractions === 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {t("retraction.clear")}
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {data.events.slice(0, 5).map((e, i) => (
                  <li key={`${i}-${e.kind}`} className="flex items-center gap-2">
                    <Badge tone="danger">{t(`retraction.${e.kind}`)}</Badge>
                    <span className="tabular-nums text-[var(--muted-foreground)]">
                      {e.tokens_before}/{e.total_tokens} tok
                    </span>
                    <span className="tabular-nums">{Math.round(e.exposure_rate * 100)}%</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-[var(--muted-foreground)]">{t("retraction.note")}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HandoffsCard({ data, loading }: { data: HandoffReport | undefined; loading: boolean }) {
  const t = useTranslations("observability");
  const types = data ? Object.entries(data.broken_by_type) : [];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Route className="h-4 w-4 text-blue-500" />
          {t("handoffs.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("handoffs.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("handoffs.broken")}
                </span>
                <Badge tone={data.total_broken === 0 ? "success" : "danger"}>
                  {data.total_broken}/{data.total_handoffs}
                </Badge>
              </div>
              <Metric label={t("handoffs.turns")} value={String(data.n_turns)} />
              <Metric label={t("handoffs.brokenTurns")} value={String(data.n_broken_turns)} />
            </div>
            {data.total_broken === 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {t("handoffs.clear")}
              </p>
            ) : (
              <ul className="flex flex-wrap gap-2 text-xs">
                {types.map(([edge, n]) => (
                  <li key={edge}>
                    <Badge tone="danger">
                      {edge} · {n}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-xs text-[var(--muted-foreground)]">{t("handoffs.note")}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TraceSnapshotCard({
  data,
  loading,
}: {
  data: SnapshotDiffReport | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitCompareArrows className="h-4 w-4 text-blue-500" />
          {t("snapshot.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading || !data ? (
          <Skeleton className="h-12 w-full" />
        ) : data.n_turns === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">{t("snapshot.empty")}</p>
        ) : (
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-6 text-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xs text-[var(--muted-foreground)]">
                  {t("snapshot.drifted")}
                </span>
                <Badge tone={data.n_drifted === 0 ? "success" : "danger"}>
                  {data.n_drifted}/{data.n_turns}
                </Badge>
              </div>
              <Metric label={t("snapshot.matching")} value={String(data.n_matching)} />
              <Metric label={t("snapshot.knownNodes")} value={String(data.known_nodes.length)} />
            </div>
            {data.n_drifted === 0 ? (
              <p className="text-xs text-emerald-600 dark:text-emerald-400">
                {t("snapshot.clear")}
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {data.drifts.slice(0, 5).map((d, i) => (
                  <li key={`${i}-${d.question.slice(0, 12)}`} className="flex items-center gap-2">
                    {d.unknown_nodes.length > 0 ? (
                      <Badge tone="danger">+{d.unknown_nodes.join(",")}</Badge>
                    ) : null}
                    {d.missing_required.length > 0 ? (
                      <Badge tone="warning">−{d.missing_required.join(",")}</Badge>
                    ) : null}
                    <span className="min-w-0 truncate text-[var(--muted-foreground)]">
                      {d.question}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GraphTopologyCard({
  data,
  loading,
}: {
  data: GraphTopology | undefined;
  loading: boolean;
}) {
  const t = useTranslations("observability");
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitFork className="h-4 w-4 text-blue-500" />
          {t("topology.title")}
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
                  {t("topology.status")}
                </span>
                <Badge tone={data.drift.drifted ? "danger" : "success"}>
                  {data.drift.drifted ? t("topology.drifted") : t("topology.pinned")}
                </Badge>
              </div>
              <Metric label={t("topology.nodes")} value={String(data.n_nodes)} />
              <Metric label={t("topology.edges")} value={String(data.n_edges)} />
            </div>
            <p className="font-mono text-[0.65rem] text-[var(--muted-foreground)]">
              {data.fingerprint.slice(0, 16)}…
            </p>
            {data.drift.drifted ? (
              <ul className="flex flex-col gap-0.5 font-mono text-[0.65rem]">
                {data.drift.added_nodes.map((n) => (
                  <li key={`+n-${n}`} className="text-emerald-600 dark:text-emerald-400">
                    + {n}
                  </li>
                ))}
                {data.drift.removed_nodes.map((n) => (
                  <li key={`-n-${n}`} className="text-red-600 dark:text-red-400">
                    − {n}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-[var(--muted-foreground)]">{t("topology.note")}</p>
            )}
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

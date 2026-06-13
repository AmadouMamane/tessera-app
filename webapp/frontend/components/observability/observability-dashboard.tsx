"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  Ban,
  Boxes,
  CalendarClock,
  ChevronRight,
  FileDown,
  Gauge,
  GitCompareArrows,
  Grid3x3,
  Landmark,
  Layers,
  ListChecks,
  Lock,
  Play,
  Radio,
  Route,
  Scale,
  ShieldCheck,
  Siren,
  Sparkles,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useState } from "react";

import { ModelComparisonTable } from "@/components/observability/eval-runs";
import { EvolutionChart } from "@/components/observability/evolution-chart";
import { FailedCasesTable, FailureDistribution } from "@/components/observability/failed-cases";
import { JudgeCalibration } from "@/components/observability/judge-calibration";
import {
  CostQualityScatter,
  EtatActuel,
  FailureBars,
  FaithGroundingScatter,
  JudgeMini,
  OverviewKpis,
  PredictiveSignals,
  PriorityCases,
  RecommendedActions,
  RegressionsByRelease,
  RootCauseDiagnostic,
  RunsPassRateTable,
} from "@/components/observability/overview-exec";
import {
  DatasetsTable,
  RunContextPanel,
  RunsCharts,
  RunsEvalTable,
  RunsKpis,
  RunsRail,
} from "@/components/observability/runs-datasets";
import {
  SignalHeatmap,
  SignalKpis,
  type SignalRow,
  SignalsRail,
  SignalsTable,
  ThemeDistribution,
  buildSignalRows,
} from "@/components/observability/signals-table";
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
  fetchCitations,
  fetchConformance,
  fetchContradictions,
  fetchCorpusFreshness,
  fetchCost,
  fetchEvalDatasets,
  fetchFailedCases,
  fetchFailureClusters,
  fetchFailurePredictor,
  fetchFirewallEfficacy,
  fetchFunnel,
  fetchIntent,
  fetchJudgeConsensus,
  fetchJudgeDrift,
  fetchLocaleFormat,
  fetchLocalization,
  fetchMetricPairs,
  fetchModelComparison,
  fetchPiiLeak,
  fetchRefusal,
  fetchRegressionRisk,
  fetchReleaseStatus,
  fetchRouting,
  fetchRuns,
  fetchSLO,
  fetchScoreSeries,
  fetchSignalStatusTrend,
  fetchToolValidity,
  fetchToxicity,
  fetchWhatChanged,
  runShadow,
} from "@/lib/api/client";
import type {
  Calibration,
  ClusterReport,
  ContradictionReport,
  FailedCasesReport,
  PIILeakSummary,
  PredictorEvaluation,
  ReleaseStatus,
  RunRegistry,
  RunSummary,
  ShadowReport,
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

export function ObservabilityDashboard() {
  const t = useTranslations("observability");
  const tq = useTranslations("quality");
  const locale = useLocale();
  const [tab, setTab] = useState<TabKey>("overview");
  const [selectedSignal, setSelectedSignal] = useState<SignalRow | null>(null);
  const [selectedRun, setSelectedRun] = useState<RunSummary | null>(null);
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();

  const slo = useQuery({
    queryKey: ["slo", asOf],
    queryFn: ({ signal }) => fetchSLO(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : POLL_MS,
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

  // Real corpus inventory — feeds the KPI strip + pipeline freshness fallback.
  const corpusFreshness = useQuery({
    queryKey: ["corpus-freshness"],
    queryFn: ({ signal }) => fetchCorpusFreshness(signal),
    refetchInterval: 60_000,
  });

  // Themed quality datasets (failure-catalogue themes × runs) — the Runs tab table.
  const evalDatasets = useQuery({
    queryKey: ["eval-datasets"],
    queryFn: ({ signal }) => fetchEvalDatasets(signal),
    refetchInterval: 60_000,
  });

  const releaseStatus = useQuery({
    queryKey: ["release-status"],
    queryFn: ({ signal }) => fetchReleaseStatus(signal),
    refetchInterval: 60_000,
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

  const toxicity = useQuery({
    queryKey: ["toxicity", asOf],
    queryFn: ({ signal }) => fetchToxicity(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
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

  // Forward-looking regression risk for the "Signaux prédictifs" column (image 00).
  const regressionRisk = useQuery({
    queryKey: ["regression-risk", asOf],
    queryFn: ({ signal }) => fetchRegressionRisk(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 30_000,
  });

  // Per-severity-band score-count trend for the Signaux KPI tiles (image 01).
  const signalStatusTrend = useQuery({
    queryKey: ["signal-status-trend", asOf],
    queryFn: ({ signal }) => fetchSignalStatusTrend(signal, asOf ?? undefined),
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

  const routing = useQuery({
    queryKey: ["routing"],
    queryFn: ({ signal }) => fetchRouting(signal),
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

  const funnel = useQuery({
    queryKey: ["funnel", asOf],
    queryFn: ({ signal }) => fetchFunnel(signal, asOf ?? undefined),
    placeholderData: keepPreviousData,
    refetchInterval: historyMode ? false : 15_000,
  });

  // Newest first for display.

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
  const signalSummary = signalRows.reduce(
    (acc, r) => {
      acc[r.status] += 1;
      acc.total += 1;
      return acc;
    },
    { ok: 0, warn: 0, crit: 0, na: 0, total: 0 },
  );
  const sloPct = slo.data && slo.data.n > 0 ? Math.round(slo.data.good_rate * 100) : null;

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
    <div className="flex flex-col gap-2">
      {/* Sticky chrome: tab bar + business actions on one row (image normative),
          the shared compact temporal rail (Live/Replay) below. */}
      <div className="sticky top-0 z-30 -mx-3 flex flex-col gap-1.5 bg-[var(--tessera-bg)] px-3 pb-1.5 pt-1.5 shadow-[0_-16px_0_0_var(--tessera-bg)]">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <TabBar active={tab} onChange={setTab} />
          <div className="flex shrink-0 items-center gap-2">
            <Button
              size="sm"
              onClick={() => setTab("runs")}
              className="h-8 gap-2 border border-[#007a55] bg-[#005c42] text-xs text-[#d6f0e3] hover:bg-[#006d4e]"
            >
              <Play className="h-3.5 w-3.5" />
              {tq("cta.runEval")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTab("models")}
              className="h-8 gap-2 text-xs"
            >
              <GitCompareArrows className="h-3.5 w-3.5" />
              {tq("cta.compareModels")}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setTab("runs")}
              className="h-8 gap-2 text-xs"
            >
              <Boxes className="h-3.5 w-3.5" />
              {tq("cta.openDataset")}
            </Button>
            <Button size="sm" onClick={downloadQualityEvidence} className="h-8 gap-2 text-xs">
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

      {/* KPI strip (unlabeled, full page width above the zones+rail — image normative) */}
      {tab === "overview" ? (
        <OverviewKpis
          sloPct={sloPct}
          faithfulness={scoreSeries.data}
          grounding={groundingSeries.data}
          hallucination={hallucinationSeries.data}
          nonRegression={releaseStatus.data?.non_regression_rate ?? null}
          nRegressions={releaseStatus.data?.n_regressions ?? null}
          kappa={calibration.data?.kappa ?? null}
          failedCount={failedCases.data?.n ?? null}
          loading={scoreSeries.isLoading}
        />
      ) : null}

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-2">
          {tab === "overview" && (
            <>
              {/* A · B · C · D as four side-by-side zones (image normative). The zones
                  are deliberately different heights ⇒ items-start (no stretch). */}
              <div className="grid items-start gap-2 lg:grid-cols-2 2xl:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_minmax(0,1.15fr)_minmax(0,1.45fr)]">
                {/* A. État actuel */}
                <EtatActuel
                  summary={signalSummary}
                  release={releaseStatus.data}
                  evolutionDelta={scoreSeries.data?.delta ?? null}
                  scorePct={sloPct}
                  series={scoreSeries.data}
                />

                {/* B. Diagnostic racine — Répartition | Calibration | Cas prioritaires,
                    then the "Qu'est-ce qui a changé / Causes probables" diagnostic. */}
                <div className="flex min-w-0 flex-col gap-2">
                  <SectionLabel>{tq("sec.diagnostic")}</SectionLabel>
                  <div className="grid items-start gap-2 sm:grid-cols-3">
                    <FailureBars report={failedCases.data} loading={failedCases.isLoading} />
                    <JudgeMini data={calibration.data} loading={calibration.isLoading} />
                    <PriorityCases
                      report={failedCases.data}
                      loading={failedCases.isLoading}
                      onOpen={setTab}
                    />
                  </div>
                  <RootCauseDiagnostic
                    whatChanged={whatChanged.data}
                    regressions={releaseStatus.data?.regressions ?? []}
                  />
                </div>

                {/* C. Signaux prédictifs */}
                <PredictiveSignals
                  series={scoreSeries.data}
                  risk={regressionRisk.data}
                  drift={judgeDrift.data}
                  predictor={failurePredictor.data}
                  intent={intent.data}
                  localization={localization.data}
                  loading={regressionRisk.isLoading}
                />

                {/* D. Actions recommandées */}
                <RecommendedActions
                  regressions={releaseStatus.data?.regressions ?? []}
                  failed={failedCases.data}
                  onOpen={setTab}
                  onEvidence={downloadQualityEvidence}
                />
              </div>
            </>
          )}

          {tab === "signals" && (
            <div className="flex flex-col gap-2">
              {/* KPI strip + registre + analytics row (normative 01). */}
              <SignalKpis
                rows={signalRows}
                trend={signalStatusTrend.data}
                catalogue={QUALITY_CATALOGUE}
              />
              <SignalsTable
                rows={signalRows}
                selectedKey={selectedSignal?.key ?? null}
                onSelect={setSelectedSignal}
              />
              <div className="grid gap-2 lg:grid-cols-3">
                <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
                <ThemeDistribution rows={signalRows} />
                <SignalHeatmap rows={signalRows} />
              </div>
            </div>
          )}

          {tab === "runs" && (
            <div className="flex flex-col gap-2">
              {/* KPI strip + [runs · datasets | contexte] + six mini-charts (image 02). */}
              <RunsKpis
                registry={runs.data}
                release={releaseStatus.data}
                freshness={corpusFreshness.data}
                datasets={evalDatasets.data}
              />
              <div className="grid gap-2 2xl:grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)] 2xl:items-start">
                <div className="flex flex-col gap-2">
                  <RunsEvalTable
                    registry={runs.data}
                    selectedId={(selectedRun ?? runs.data?.runs[0])?.run_id ?? null}
                    onSelect={setSelectedRun}
                  />
                  <DatasetsTable report={evalDatasets.data} />
                </div>
                <RunContextPanel
                  run={selectedRun ?? runs.data?.runs[0]}
                  release={releaseStatus.data}
                  onEvidence={downloadQualityEvidence}
                />
              </div>
              <RunsCharts
                registry={runs.data}
                models={modelComparison.data}
                datasets={evalDatasets.data}
              />
            </div>
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

        {tab === "signals" ? (
          <SignalsRail
            selected={selectedSignal}
            rows={signalRows}
            failed={failedCases.data}
            release={releaseStatus.data}
            whatChanged={whatChanged.data}
            onOpen={setTab}
            onEvidence={downloadQualityEvidence}
          />
        ) : tab === "runs" ? (
          <RunsRail
            registry={runs.data}
            datasets={evalDatasets.data}
            release={releaseStatus.data}
          />
        ) : (
          <RightRail
            failed={failedCases.data}
            release={releaseStatus.data}
            whatChanged={whatChanged.data}
            runs={runs.data}
            onOpen={setTab}
            onEvidence={downloadQualityEvidence}
          />
        )}
      </div>

      {/* Full-width analytics row below the [main · rail] grid (image normative):
          Pass-rate des runs | Évolution | Répartition | Faith×Grounding | Régressions
          par release | Coût vs qualité — six charts spanning the whole page width. */}
      {tab === "overview" ? (
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
          <RunsPassRateTable registry={runs.data} loading={runs.isLoading} />
          <EvolutionChart series={scoreSeries.data} loading={scoreSeries.isLoading} />
          <FailureDistribution report={failedCases.data} loading={failedCases.isLoading} />
          <FaithGroundingScatter pairs={metricPairs.data} loading={metricPairs.isLoading} />
          <RegressionsByRelease release={releaseStatus.data} loading={releaseStatus.isLoading} />
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

/** Right rail (image normative): Derniers problèmes · Release actuelle · Actions
 * rapides · Activités récentes — all fed by live data, links into the tabs. */
function RightRail({
  failed,
  release,
  whatChanged,
  runs,
  onOpen,
  onEvidence,
}: {
  failed: FailedCasesReport | undefined;
  release: ReleaseStatus | undefined;
  whatChanged: WhatChanged | undefined;
  runs: RunRegistry | undefined;
  onOpen: (tab: TabKey) => void;
  onEvidence: () => void;
}) {
  const tq = useTranslations("quality");
  const current = release?.current ?? null;
  const nReg = release?.n_regressions ?? 0;
  const blocked = nReg > 0;
  const impact = nReg === 0 ? "low" : nReg <= 2 ? "medium" : "high";
  const problems = (failed?.cases ?? []).slice(0, 4);
  const quick: { label: string; icon: typeof Activity; action: () => void }[] = [
    { label: tq("rr.linkRuns"), icon: Activity, action: () => onOpen("runs") },
    { label: tq("rr.linkTraces"), icon: Route, action: () => onOpen("runs") },
    { label: tq("rr.linkDataset"), icon: Boxes, action: () => onOpen("runs") },
    { label: tq("rr.linkEvidence"), icon: FileDown, action: onEvidence },
  ];
  // Recent activity, derived from real data: the latest run, the release, the diff.
  const latestRun = [...(runs?.runs ?? [])].sort((a, b) => b.run_at.localeCompare(a.run_at))[0];
  const activity: { key: string; label: string; detail: string }[] = [];
  if (latestRun) {
    activity.push({
      key: "run",
      label: tq("rr.actRun", { n: latestRun.total }),
      detail: latestRun.run_at.slice(0, 10),
    });
  }
  if (current) {
    activity.push({
      key: "release",
      label: tq(blocked ? "rr.actReleaseBlocked" : "rr.actReleaseDeployed", {
        v: current.version,
      }),
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
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-28">
        {/* Derniers problèmes */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.problems")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1">
            {problems.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("rr.noProblems")}</p>
            ) : (
              problems.map((p) => (
                <div key={p.case_id} className="flex items-center gap-1.5 text-[0.7rem]">
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      p.severity === "critical"
                        ? "bg-red-500"
                        : p.severity === "high"
                          ? "bg-amber-500"
                          : "bg-[var(--muted-foreground)]"
                    }`}
                  />
                  <span className="min-w-0 flex-1 truncate">{p.title}</span>
                  <span className="shrink-0 text-[0.6rem] text-[var(--muted-foreground)]">
                    {p.severity}
                  </span>
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
              <CardTitle className="text-sm">{tq("rr.release")}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1 text-[0.7rem]">
              <div className="flex items-center gap-2">
                <span className="font-serif text-base font-semibold tabular-nums">
                  {current.version}
                </span>
                <Badge tone={blocked ? "danger" : "success"}>
                  {blocked ? tq("rr.blocked") : tq("rr.inProd")}
                </Badge>
              </div>
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="text-[var(--muted-foreground)]">{tq("rr.impact")}</span>
                <span
                  className={
                    impact === "high"
                      ? "text-red-500"
                      : impact === "medium"
                        ? "text-amber-500"
                        : "text-[var(--muted-foreground)]"
                  }
                >
                  {tq(`exec.etat.${impact}`)}
                </span>
              </div>
              {current.date ? (
                <div className="flex items-center justify-between gap-2 text-xs">
                  <span className="text-[var(--muted-foreground)]">{tq("rr.openedAt")}</span>
                  <span className="tabular-nums">{current.date}</span>
                </div>
              ) : null}
              <RailLink onClick={() => onOpen("models")}>{tq("rr.seeReleases")}</RailLink>
            </CardContent>
          </Card>
        ) : null}

        {/* Actions rapides */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("rr.actions")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-0.5">
            {quick.map((q) => (
              <button
                key={q.label}
                type="button"
                onClick={q.action}
                className="flex items-center gap-2 rounded-md px-1.5 py-0.5 text-left text-[0.7rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
              >
                <q.icon className="h-3 w-3 shrink-0" />
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
          <CardContent className="flex flex-col gap-1">
            {activity.length === 0 ? (
              <p className="text-xs text-[var(--muted-foreground)]">{tq("rr.noActivity")}</p>
            ) : (
              activity.slice(0, 3).map((a) => (
                <div key={a.key} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tessera-green)]" />
                  <span className="min-w-0 flex-1 truncate text-[0.7rem]">{a.label}</span>
                  <span className="shrink-0 font-mono text-[0.6rem] text-[var(--muted-foreground)]">
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
/** Span both columns of a section grid (for wide tables / panels). */
function FullWidth({ children }: { children: ReactNode }) {
  return <div className="lg:col-span-2">{children}</div>;
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
